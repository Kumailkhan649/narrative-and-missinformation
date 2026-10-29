from .contracts import InferRequest,ReviewFeedback
from .embeddings import resolve_embeddings
from .topics import cluster_topics
from .evolution import topic_evolution
from .trends import detect_spikes
from .narratives import track_narratives
from .coordination import detect_coordination
from .flags import narrative_flags,bias_flags
from .envelope import build_event
from .store import EventStore
from .validation import apply_feedback
from .evaluation import flag_precision

class AI08Service:
    def __init__(self,store=None):
        self.store=store if store is not None else EventStore()

    def infer(self,request:InferRequest):
        records=request.records
        config=request.config
        vectors=resolve_embeddings(records,request.embedding_vectors,config.embedding_model_path)
        topics,assignments=cluster_topics(records,vectors,config)
        timelines=topic_evolution(topics,config)
        spikes=detect_spikes(records,request.mention_counts,config)
        narratives=track_narratives(records,vectors,config)
        coordination=detect_coordination(records,config)
        flags=narrative_flags(narratives,request.reference_claims,config)+bias_flags(records,config,assignments)
        events=[]
        revision=f"{config.version}:{config.signature()}"
        for topic in topics:
            members=topic["members"]
            payload={key:value for key,value in topic.items() if key!="members"}
            events.append(build_event("topic",topic["topic_id"],payload,members,revision,topic["confidence"],"online clustering"))
            rows=[row for row in timelines if row["topic_id"]==topic["topic_id"]]
            events.append(build_event("topic_evolution",topic["topic_id"],{"topic_id":topic["topic_id"],"windows":rows},members,revision,topic["confidence"],"rolling windows"))
        for spike in spikes:
            matched=[r for r in records if spike["t_start"]<=r.t_start<spike["t_end"] and (spike["subject"]=="overall" or spike["subject"] in r.entities or spike["subject"] in r.tags)]
            if matched:
                events.append(build_event("spike",f"{spike['subject']}:{spike['t_start']}:{spike['type']}",spike,matched,revision,spike["confidence"],"seasonal baseline"))
        for narrative in narratives:
            payload={key:value for key,value in narrative.items() if key!="members"}
            events.append(build_event("narrative",narrative["narrative_id"],payload,narrative["members"],revision,narrative["confidence"],"claim matching"))
        for group in coordination:
            payload={key:value for key,value in group.items() if key!="members"}
            events.append(build_event("coordination",":".join(group["accounts"]),payload,group["members"],revision,group["confidence"],"near-duplicate and burst"))
        for flag in flags:
            payload={key:value for key,value in flag.items() if key!="members"}
            payload["calibration_status"]="unvalidated"
            events.append(build_event("risk_flag",flag["flag_id"],payload,flag["members"],revision,flag["confidence"],"provisional risk rules"))
        return self.store.persist_inference(records,vectors,events)

    def review(self,feedback:ReviewFeedback):
        return apply_feedback(self.store,feedback)

    def evaluate(self):
        return flag_precision(self.store.reviews())

    def queue(self,request:InferRequest):
        return self.store.enqueue(request)

    def run_pending(self,limit=100):
        completed=[]
        for request_id,request in self.store.pending_requests(limit):
            events=self.infer(request)
            self.store.complete_request(request_id,events)
            completed.append({"request_id":request_id,"event_ids":[event.event_id for event in events]})
        return completed

    def publish_pending(self,publisher,limit=100):
        published=[]
        for event in self.store.unpublished_events(limit):
            publisher(event)
            self.store.mark_published(event.event_id)
            published.append(event.event_id)
        return published
