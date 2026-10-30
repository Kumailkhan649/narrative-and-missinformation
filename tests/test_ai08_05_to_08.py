import unittest
from ai08.contracts import EnrichedRecord, InferRequest, ReferenceClaim, ReviewFeedback
from ai08.evaluation import flag_precision
from ai08.service import AI08Service
from tests.support import MemoryEventStore

def make_record(identifier, source, text, minute, source_type="tv", account_id=None, sentiment=None):
    stamp = 1760000000000 + minute * 60000
    return EnrichedRecord(record_id=identifier, source_type=source_type, source_id=source, t_start=stamp, t_end=stamp+10000, language="English", text=text, embedding=[1.0, 0.0], account_id=account_id, target_sentiment=sentiment or {}, evidence_uri=f"synthetic:{identifier}")

class PendingActivityTests(unittest.TestCase):
    def setUp(self):
        self.service = AI08Service(store=MemoryEventStore())

    def make_flag(self):
        claim = "According to the report public spending increased 50 percent"
        records = [make_record("m1", "s1", claim, 0), make_record("m2", "s2", claim, 1)]
        reference = ReferenceClaim(claim="Synthetic contradiction", source_id="reference-1", evidence_uri="synthetic:reference", refutes=[claim])
        events = self.service.infer(InferRequest(records=records, reference_claims=[reference]))
        return next(e for e in events if e.payload.get("type") == "potential_misinformation")

    def test_05_risk_flag_requires_cited_contradiction_and_preserves_evidence(self):
        flag = self.make_flag()
        self.assertEqual(flag.review_status, "pending")
        self.assertEqual(flag.payload["calibration_status"], "unvalidated")
        self.assertEqual(flag.payload["contradicting_sources"][0]["evidence_uri"], "synthetic:reference")
        self.assertEqual({e["record_id"] for e in flag.payload["supporting_evidence"]}, {"m1", "m2"})

    def test_05_unmatched_reference_cannot_trigger_misinformation(self):
        claim = "According to the report public spending increased 50 percent"
        records = [make_record("n1", "s1", claim, 0), make_record("n2", "s2", claim, 1)]
        reference = ReferenceClaim(claim="Unrelated reference", source_id="reference-1", evidence_uri="synthetic:reference", refutes=["Completely unrelated assertion"])
        events = self.service.infer(InferRequest(records=records, reference_claims=[reference]))
        self.assertFalse(any(e.payload.get("type") == "potential_misinformation" for e in events))

    def test_05_bias_flag_includes_source_specific_evidence(self):
        claim = "According to the report public spending increased 50 percent"
        records = [make_record("b1", "s1", claim, 0, sentiment={"Policy": 0.9}), make_record("b2", "s2", claim, 1, sentiment={"Policy": -0.9})]
        events = self.service.infer(InferRequest(records=records))
        flag = next(e for e in events if e.payload.get("type") == "possible_tone_bias")
        self.assertEqual(set(flag.payload["source_mean_sentiment"]), {"s1", "s2"})
        self.assertEqual({e["record_id"] for e in flag.payload["supporting_evidence"]}, {"b1", "b2"})
        self.assertEqual(flag.payload["calibration_status"], "unvalidated")

    def test_06_reject_review_persists_and_is_not_double_counted(self):
        flag = self.make_flag()
        feedback = ReviewFeedback(event_id=flag.event_id, decision="reject", reviewer="synthetic-analyst", time=1760000100000)
        reviewed = self.service.review(feedback)
        self.assertEqual(reviewed.review_status, "rejected")
        self.assertEqual(self.service.review(feedback).review_status, "rejected")
        self.assertEqual(self.service.evaluate()["reviewed"], 1)
        self.assertEqual(self.service.evaluate()["precision"], 0.0)
        self.assertEqual(self.service.store.get(flag.event_id).review_status, "rejected")

    def test_06_reviewer_cannot_reverse_existing_final_decision(self):
        flag = self.make_flag()
        self.service.review(ReviewFeedback(event_id=flag.event_id, decision="accept", reviewer="synthetic-analyst", time=1760000100000))
        with self.assertRaisesRegex(ValueError, "already been reviewed"):
            self.service.review(ReviewFeedback(event_id=flag.event_id, decision="reject", reviewer="another-analyst", time=1760000200000))

    def test_07_coordination_requires_distinct_digital_accounts(self):
        text = "Coordinated announcement from a synthetic test account"
        records = [make_record("c1", "s1", text, 0, "digital", "acc1"), make_record("c2", "s2", text, 1, "digital", "acc2"), make_record("c3", "s3", text, 2, "digital", "acc3")]
        events = self.service.infer(InferRequest(records=records))
        groups = [e for e in events if e.payload.get("signal_type") == "coordination"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0].payload["accounts"]), {"acc1", "acc2", "acc3"})
        records[2] = make_record("c3", "s3", text, 2, "tv", "acc3")
        other = AI08Service(store=MemoryEventStore()).infer(InferRequest(records=records))
        self.assertFalse(any(e.payload.get("signal_type") == "coordination" for e in other))

    def test_08_precision_is_only_analyst_reviewed_flag_acceptance(self):
        reviews = [{"event_id": "x1", "decision": "accept", "time": 1}, {"event_id": "x2", "decision": "reject", "time": 2}, {"event_id": "x3", "decision": "correct", "time": 3}]
        result = flag_precision(reviews)
        self.assertEqual(result["confirmed"], 1)
        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["corrected"], 1)
        self.assertEqual(result["reviewed"], 3)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["target"], "not agreed")

    def test_08_no_labelled_reviews_does_not_invent_precision(self):
        result = flag_precision([])
        self.assertIsNone(result["precision"])
        self.assertEqual(result["reviewed"], 0)
        self.assertEqual(result["target"], "not agreed")