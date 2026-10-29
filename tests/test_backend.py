import unittest
from concurrent.futures import ThreadPoolExecutor
from pydantic import ValidationError
from ai08.config import AI08Config
from ai08.contracts import EnrichedRecord,InferRequest,MentionCount,ReferenceClaim,ReviewFeedback
from ai08.trends import detect_spikes
from ai08.service import AI08Service
from tests.support import MemoryEventStore

def record(identifier,source,text,minute,embedding,source_type="tv",account_id=None,target_sentiment=None):
    stamp=1760000000000+minute*60000
    return EnrichedRecord(record_id=identifier,source_type=source_type,source_id=source,t_start=stamp,t_end=stamp+10000,language="Urdu",text=text,entities=["Policy"],tags=["Issue"],keywords=["Claim"],sentiment=-0.5,embedding=embedding,account_id=account_id,target_sentiment=target_sentiment or {},evidence_uri=f"evidence:{identifier}")

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.service=AI08Service(store=MemoryEventStore())

    def tearDown(self):
        self.service.store.close()

    def test_input_validation(self):
        invalid=record("bad","a","claim 5",10,[1,0]).model_dump()
        invalid["t_end"]=0
        with self.assertRaises(ValidationError):
            EnrichedRecord.model_validate(invalid)

    def test_topics_and_narratives_are_idempotent(self):
        claim="کے مطابق منصوبے پر 50 فیصد لاگت بڑھی"
        records=[record("a","channel-a",claim,0,[1,0]),record("b","channel-b",claim,1,[0.99,0.01],"digital",target_sentiment={"Policy":0.9}),record("c","channel-c",claim,2,[0.99,0.01],target_sentiment={"Policy":-0.9})]
        request=InferRequest(records=records,reference_claims=[ReferenceClaim(claim="Verified report does not support the claim",source_id="reference-1",evidence_uri="reference:1",refutes=[claim])])
        first=self.service.infer(request)
        second=self.service.infer(request)
        self.assertEqual([e.event_id for e in first],[e.event_id for e in second])
        self.assertTrue(any(e.payload["signal_type"]=="topic" for e in first))
        self.assertTrue(any(e.payload["signal_type"]=="narrative" for e in first))
        self.assertTrue(any(e.payload.get("type")=="potential_misinformation" for e in first))
        self.assertTrue(any(e.payload.get("type")=="possible_tone_bias" for e in first))
        self.assertTrue(all(len(type(e).model_fields)==15 for e in first))
        self.assertTrue(all(e.review_status=="pending" for e in first))

    def test_no_false_verdict_without_reference(self):
        records=[record("a","s1","کے مطابق منصوبے پر 50 فیصد لاگت بڑھی",0,[1,0]),record("b","s2","کے مطابق منصوبے پر 50 فیصد لاگت بڑھی",1,[1,0])]
        events=self.service.infer(InferRequest(records=records))
        self.assertFalse(any(e.payload.get("type")=="potential_misinformation" for e in events))

    def test_coordination_groups_accounts(self):
        text="Same announcement 50 percent"
        records=[record(str(i),f"s{i}",text,i,[1,0],"digital",f"account-{i}") for i in range(3)]
        events=self.service.infer(InferRequest(records=records))
        signals=[e for e in events if e.payload["signal_type"]=="coordination"]
        self.assertEqual(len(signals),1)
        self.assertEqual(len(signals[0].payload["accounts"]),3)

    def test_validation_and_evaluation(self):
        claim="News states 50 percent"
        records=[record("a","s1",claim,0,[1,0]),record("b","s2",claim,1,[1,0])]
        reference=ReferenceClaim(claim="This claim is contradicted",source_id="ref",evidence_uri="ref:1",refutes=[claim])
        events=self.service.infer(InferRequest(records=records,reference_claims=[reference]))
        flagged=next(e for e in events if e.payload.get("type")=="potential_misinformation")
        feedback=ReviewFeedback(event_id=flagged.event_id,decision="correct",corrected_value={"risk_score":0.1},reviewer="analyst",time=1760000100000)
        corrected=self.service.review(feedback)
        self.assertEqual(corrected.payload["supersedes"],flagged.event_id)
        self.assertEqual(corrected.event_id,self.service.review(feedback).event_id)
        self.assertEqual(self.service.store.get(flagged.event_id).review_status,"corrected")
        self.assertEqual(self.service.evaluate()["corrected"],1)
        self.assertIsNone(self.service.evaluate()["precision"])

    def test_missing_embeddings_fail(self):
        incomplete=record("a","s1","claim 50",0,[1,0]).model_copy(update={"embedding":None})
        with self.assertRaisesRegex(ValueError,"missing embeddings"):
            self.service.infer(InferRequest(records=[incomplete],config=AI08Config()))

    def test_spike_uses_weekday_hour_history(self):
        base=1760000000000//3600000*3600000
        counts=[MentionCount(subject="overall",t_start=base+week*7*86400000,count=1) for week in range(6)]
        counts.append(MentionCount(subject="overall",t_start=base+6*7*86400000,count=20))
        spikes=detect_spikes([],counts,AI08Config())
        self.assertEqual(len(spikes),1)
        self.assertEqual(spikes[0]["observed"],20)
        self.assertEqual(spikes[0]["baseline"],"day_of_week_and_hour")

    def test_different_numbers_do_not_merge(self):
        records=[record("a","s1","According to the report cost rose 50 percent",0,[1,0]),record("b","s2","According to the report cost rose 5 percent",1,[1,0])]
        events=self.service.infer(InferRequest(records=records))
        self.assertFalse(any(e.payload["signal_type"]=="narrative" for e in events))

    def test_same_number_different_claims_do_not_merge(self):
        records=[record("a","s1","According to the report 50 people were injured",0,[1,0]),record("b","s2","According to the report 50 people attended a festival",1,[1,0])]
        events=self.service.infer(InferRequest(records=records))
        self.assertFalse(any(e.payload["signal_type"]=="narrative" for e in events))

    def test_reviewed_status_survives_reinference(self):
        claim="According to the report 50 percent of funds were spent"
        records=[record("a","s1",claim,0,[1,0]),record("b","s2",claim,1,[1,0])]
        reference=ReferenceClaim(claim="Verified statement disputes claim",source_id="ref",evidence_uri="ref:1",refutes=[claim])
        request=InferRequest(records=records,reference_claims=[reference])
        flag=next(e for e in self.service.infer(request) if e.payload.get("type")=="potential_misinformation")
        self.service.review(ReviewFeedback(event_id=flag.event_id,decision="accept",reviewer="analyst",time=1760000100000))
        repeated=next(e for e in self.service.infer(request) if e.event_id==flag.event_id)
        self.assertEqual(repeated.review_status,"accepted")
        self.assertEqual(self.service.evaluate()["precision"],1.0)

    def test_non_flag_review_is_rejected(self):
        record_item=record("a","s1","According to report 50 percent",0,[1,0])
        topic=self.service.infer(InferRequest(records=[record_item]))[0]
        with self.assertRaisesRegex(ValueError,"only risk flags"):
            self.service.review(ReviewFeedback(event_id=topic.event_id,decision="accept",reviewer="analyst",time=1760000100000))
        self.assertIsNone(self.service.evaluate()["precision"])

    def test_changed_config_cannot_reuse_old_id(self):
        claim="According to report costs increased 50 percent"
        records=[record("a","s1",claim,0,[1,0]),record("b","s2",claim,1,[1,0])]
        reference=ReferenceClaim(claim="Reference disagrees",source_id="ref",evidence_uri="ref:1",refutes=[claim])
        make=lambda risk:InferRequest(records=records,reference_claims=[reference],config=AI08Config(contradiction_risk=risk))
        flag1=next(e for e in self.service.infer(make(0.85)) if e.payload.get("type")=="potential_misinformation")
        flag2=next(e for e in self.service.infer(make(0.20)) if e.payload.get("type")=="potential_misinformation")
        self.assertNotEqual(flag1.event_id,flag2.event_id)
        self.assertEqual(self.service.store.get(flag1.event_id).payload["risk_score"],0.85)
        self.assertEqual(self.service.store.get(flag2.event_id).payload["risk_score"],0.20)

    def test_coordination_chain_is_not_one_burst(self):
        text="Coordinated announcement 50 percent"
        records=[record("a","s1",text,0,[1,0],"digital","acc1"),record("b","s2",text,14,[1,0],"digital","acc2"),record("c","s3",text,28,[1,0],"digital","acc3")]
        events=self.service.infer(InferRequest(records=records))
        self.assertFalse(any(e.payload["signal_type"]=="coordination" for e in events))

    def test_bias_compares_matching_topic_only(self):
        records=[record("a","s1","According to report 50 percent",0,[1,0],target_sentiment={"Policy":0.9}),record("b","s2","According to report 5 percent",1,[0,1],target_sentiment={"Policy":-0.9})]
        events=self.service.infer(InferRequest(records=records))
        self.assertFalse(any(e.payload.get("type")=="possible_tone_bias" for e in events))

    def test_concurrent_inference_is_idempotent(self):
        one=record("a","s1","According to report 50 percent",0,[1,0])
        request=InferRequest(records=[one])
        with ThreadPoolExecutor(max_workers=6) as executor:
            outputs=list(executor.map(self.service.infer,[request]*12))
        self.assertEqual(len({output[0].event_id for output in outputs}),1)

    def test_nearline_queue_and_outbox(self):
        one=record("a","s1","According to report 50 percent",0,[1,0])
        request=InferRequest(records=[one])
        first_id=self.service.queue(request)
        self.assertEqual(first_id,self.service.queue(request))
        completed=self.service.run_pending()
        self.assertEqual(len(completed),1)
        self.assertEqual(completed[0]["request_id"],first_id)
        self.assertEqual(completed[0]["event_ids"],self.service.store.queued_result_ids(first_id))
        self.assertEqual(self.service.run_pending(),[])
        delivered=[]
        published=self.service.publish_pending(delivered.append)
        self.assertEqual({e.event_id for e in delivered},set(published))
        self.assertEqual(self.service.publish_pending(delivered.append),[])

    def test_publisher_failure_keeps_outbox_event(self):
        one=record("a","s1","According to report 50 percent",0,[1,0])
        self.service.infer(InferRequest(records=[one]))
        def fail(event):
            raise RuntimeError("not delivered")
        with self.assertRaisesRegex(RuntimeError,"not delivered"):
            self.service.publish_pending(fail)
        self.assertGreater(len(self.service.store.unpublished_events()),0)

    def test_event_id_collision_is_rejected(self):
        one=record("a","s1","According to report 50 percent",0,[1,0])
        event=self.service.infer(InferRequest(records=[one]))[0]
        modified=event.model_copy(update={"payload":{**event.payload,"size":999}})
        with self.assertRaisesRegex(ValueError,"event_id collision"):
            self.service.store.save(modified)

    def test_embeddings_saved_in_processed_store(self):
        item=record("a","s1","According to report 50 percent",0,[1,0])
        self.service.infer(InferRequest(records=[item]))
        self.assertIn(item.record_id,self.service.store.embeddings)

    def test_double_review_is_rejected(self):
        claim="According to report spending rose 50 percent"
        records=[record("a","s1",claim,0,[1,0]),record("b","s2",claim,1,[1,0])]
        reference=ReferenceClaim(claim="Disputed",source_id="ref",evidence_uri="ref:1",refutes=[claim])
        flag=next(event for event in self.service.infer(InferRequest(records=records,reference_claims=[reference])) if event.payload.get("type")=="potential_misinformation")
        self.service.review(ReviewFeedback(event_id=flag.event_id,decision="accept",reviewer="reviewer1",time=1760000100000))
        with self.assertRaisesRegex(ValueError,"already been reviewed"):
            self.service.review(ReviewFeedback(event_id=flag.event_id,decision="reject",reviewer="reviewer2",time=1760000200000))

if __name__=="__main__":
    unittest.main()
