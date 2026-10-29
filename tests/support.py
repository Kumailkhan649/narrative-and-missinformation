import hashlib
import json
from datetime import datetime,timezone
from threading import RLock
from ai08.contracts import EventEnvelope,InferRequest

class MemoryEventStore:
    def __init__(self):
        self.lock=RLock()
        self.events={}
        self.reviews_log={}
        self.queue_data={}
        self.outbox=set()
        self.embeddings={}

    def persist_inference(self,records,vectors,events):
        with self.lock:
            for record in records:
                value=(list(vectors[record.record_id]),"upstream","unverified")
                previous=self.embeddings.get(record.record_id)
                if previous is not None and previous!=value:
                    raise ValueError("record_id collision with different embedding")
            for event in events:
                previous=self.events.get(event.event_id)
                if previous is not None:
                    excluded={"created_at","review_status"}
                    if previous.model_dump(exclude=excluded,by_alias=True)!=event.model_dump(exclude=excluded,by_alias=True):
                        raise ValueError("event_id collision with different payload")
            for record in records:
                self.embeddings[record.record_id]=(list(vectors[record.record_id]),"upstream","unverified")
            return [self.save(event) for event in events]

    def save(self,event):
        with self.lock:
            previous=self.events.get(event.event_id)
            if previous is not None:
                excluded={"created_at","review_status"}
                if previous.model_dump(exclude=excluded,by_alias=True)!=event.model_dump(exclude=excluded,by_alias=True):
                    raise ValueError("event_id collision with different payload")
                return previous
            self.events[event.event_id]=event
            self.outbox.add(event.event_id)
            return event

    def get(self,event_id):
        with self.lock:
            return self.events.get(event_id)

    def apply_decision(self,review_id,feedback):
        with self.lock:
            original=self.get(feedback.event_id)
            if original is None:
                raise KeyError(feedback.event_id)
            if original.payload.get("signal_type")!="risk_flag":
                raise ValueError("only risk flags can be reviewed")
            if review_id in self.reviews_log:
                return self.get(review_id) if feedback.decision=="correct" else original
            if original.review_status!="pending":
                raise ValueError("risk flag has already been reviewed")
            status={"accept":"accepted","correct":"corrected","reject":"rejected"}[feedback.decision]
            updated=original.model_copy(update={"review_status":status})
            self.events[original.event_id]=updated
            self.reviews_log[review_id]=feedback
            if feedback.decision!="correct":
                return updated
            corrected=original.model_copy(update={"event_id":review_id,"payload":{**original.payload,**feedback.corrected_value,"supersedes":original.event_id},"review_status":"corrected","created_at":datetime.now(timezone.utc).isoformat()})
            self.events[review_id]=corrected
            self.outbox.add(review_id)
            return corrected

    def enqueue(self,request:InferRequest):
        content=request.model_dump(mode="json")
        request_id=hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()
        with self.lock:
            self.queue_data.setdefault(request_id,[request,None])
        return request_id

    def pending_requests(self,limit=100):
        with self.lock:
            return [(key,value[0]) for key,value in list(self.queue_data.items()) if value[1] is None][:limit]

    def complete_request(self,request_id,events):
        with self.lock:
            self.queue_data[request_id][1]=[event.event_id for event in events]

    def queued_result_ids(self,request_id):
        with self.lock:
            return self.queue_data[request_id][1]

    def unpublished_events(self,limit=100):
        with self.lock:
            return [self.events[key] for key in sorted(self.outbox)[:limit]]

    def mark_published(self,event_id):
        with self.lock:
            self.outbox.discard(event_id)

    def reviews(self,flag_only=True):
        with self.lock:
            return [{"event_id":value.event_id,"decision":value.decision,"reviewer":value.reviewer,"time":value.time,"corrected_value":value.corrected_value} for value in self.reviews_log.values()]

    def save_embedding(self,record_id,vector,model_name="upstream",model_version="unverified"):
        with self.lock:
            value=(list(vector),model_name,model_version)
            previous=self.embeddings.setdefault(record_id,value)
            if previous!=value:
                raise ValueError("record_id collision with different embedding")

    def close(self):
        return None
