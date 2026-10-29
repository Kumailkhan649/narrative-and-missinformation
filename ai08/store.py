import hashlib
import json
import os
from datetime import datetime,timezone
from math import isfinite
from .contracts import EventEnvelope,InferRequest

def as_json(value):
    from psycopg.types.json import Jsonb
    return Jsonb(value)

class EventStore:
    def __init__(self,dsn=None):
        self.dsn=dsn or os.environ.get("DATABASE_URL")
        if not self.dsn:
            raise RuntimeError("DATABASE_URL is required")

    def _connect(self):
        from psycopg import connect
        from psycopg.rows import dict_row
        return connect(self.dsn,row_factory=dict_row)

    def _save_event(self,connection,event):
        connection.execute("INSERT INTO processed.ai08_events(event_id,content) VALUES (%s,%s) ON CONFLICT DO NOTHING",(event.event_id,as_json(event.model_dump(mode="json",by_alias=True))))
        row=connection.execute("SELECT content FROM processed.ai08_events WHERE event_id=%s FOR UPDATE",(event.event_id,)).fetchone()
        previous=EventEnvelope.model_validate(row["content"])
        excluded={"created_at","review_status"}
        if previous.model_dump(exclude=excluded,by_alias=True)!=event.model_dump(exclude=excluded,by_alias=True):
            raise ValueError("event_id collision with different payload")
        connection.execute("INSERT INTO processed.ai08_signal_outbox(event_id) VALUES (%s) ON CONFLICT DO NOTHING",(event.event_id,))
        return previous

    def save(self,event):
        with self._connect() as connection:
            return self._save_event(connection,event)

    def persist_inference(self,records,vectors,events):
        with self._connect() as connection:
            for record in records:
                self._save_embedding(connection,record.record_id,vectors[record.record_id])
            return [self._save_event(connection,event) for event in events]

    def get(self,event_id):
        with self._connect() as connection:
            row=connection.execute("SELECT content FROM processed.ai08_events WHERE event_id=%s",(event_id,)).fetchone()
            return EventEnvelope.model_validate(row["content"]) if row else None

    def apply_decision(self,review_id,feedback):
        with self._connect() as connection:
            with connection.transaction():
                row=connection.execute("SELECT content FROM processed.ai08_events WHERE event_id=%s FOR UPDATE",(feedback.event_id,)).fetchone()
                if row is None:
                    raise KeyError(feedback.event_id)
                original=EventEnvelope.model_validate(row["content"])
                if original.payload.get("signal_type")!="risk_flag":
                    raise ValueError("only risk flags can be reviewed")
                existing=connection.execute("SELECT 1 FROM processed.ai08_reviews WHERE review_id=%s",(review_id,)).fetchone()
                if existing:
                    if feedback.decision=="correct":
                        result=connection.execute("SELECT content FROM processed.ai08_events WHERE event_id=%s",(review_id,)).fetchone()
                        return EventEnvelope.model_validate(result["content"])
                    return original
                if original.review_status!="pending":
                    raise ValueError("risk flag has already been reviewed")
                status={"accept":"accepted","correct":"corrected","reject":"rejected"}[feedback.decision]
                updated=original.model_copy(update={"review_status":status})
                corrected=None
                if feedback.decision=="correct":
                    corrected=original.model_copy(update={"event_id":review_id,"payload":{**original.payload,**feedback.corrected_value,"supersedes":original.event_id},"review_status":"corrected","created_at":datetime.now(timezone.utc).isoformat()})
                connection.execute("UPDATE processed.ai08_events SET content=%s WHERE event_id=%s",(as_json(updated.model_dump(mode="json",by_alias=True)),original.event_id))
                connection.execute("INSERT INTO processed.ai08_reviews(review_id,event_id,decision,reviewer,reviewed_at,corrected_value) VALUES (%s,%s,%s,%s,%s,%s)",(review_id,feedback.event_id,feedback.decision,feedback.reviewer,feedback.time,as_json(feedback.corrected_value) if feedback.corrected_value is not None else None))
                if corrected:
                    connection.execute("INSERT INTO processed.ai08_events(event_id,content) VALUES (%s,%s)",(corrected.event_id,as_json(corrected.model_dump(mode="json",by_alias=True))))
                    connection.execute("INSERT INTO processed.ai08_signal_outbox(event_id) VALUES (%s)",(corrected.event_id,))
                return corrected or updated

    def enqueue(self,request:InferRequest):
        content=request.model_dump(mode="json")
        canonical=json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(",",":"))
        request_id=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute("INSERT INTO processed.ai08_inference_queue(request_id,content) VALUES (%s,%s) ON CONFLICT DO NOTHING",(request_id,as_json(content)))
        return request_id

    def pending_requests(self,limit=100):
        with self._connect() as connection:
            rows=connection.execute("SELECT request_id,content FROM processed.ai08_inference_queue WHERE processed=false ORDER BY created_at,request_id LIMIT %s",(limit,)).fetchall()
            return [(row["request_id"],InferRequest.model_validate(row["content"])) for row in rows]

    def complete_request(self,request_id,events):
        with self._connect() as connection:
            connection.execute("UPDATE processed.ai08_inference_queue SET processed=true,result_ids=%s WHERE request_id=%s",(as_json([event.event_id for event in events]),request_id))

    def queued_result_ids(self,request_id):
        with self._connect() as connection:
            row=connection.execute("SELECT result_ids FROM processed.ai08_inference_queue WHERE request_id=%s",(request_id,)).fetchone()
            return row["result_ids"] if row else None

    def unpublished_events(self,limit=100):
        with self._connect() as connection:
            rows=connection.execute("SELECT e.content FROM processed.ai08_signal_outbox o JOIN processed.ai08_events e ON e.event_id=o.event_id WHERE o.published=false ORDER BY o.created_at,o.event_id LIMIT %s",(limit,)).fetchall()
            return [EventEnvelope.model_validate(row["content"]) for row in rows]

    def mark_published(self,event_id):
        with self._connect() as connection:
            connection.execute("UPDATE processed.ai08_signal_outbox SET published=true WHERE event_id=%s",(event_id,))

    def reviews(self,flag_only=True):
        with self._connect() as connection:
            rows=connection.execute("SELECT r.event_id,r.decision,r.reviewer,r.reviewed_at,r.corrected_value,e.content FROM processed.ai08_reviews r JOIN processed.ai08_events e ON e.event_id=r.event_id ORDER BY r.reviewed_at,r.review_id").fetchall()
            return [{"event_id":row["event_id"],"decision":row["decision"],"reviewer":row["reviewer"],"time":row["reviewed_at"],"corrected_value":row["corrected_value"]} for row in rows if not flag_only or row["content"]["payload"].get("signal_type")=="risk_flag"]

    def _save_embedding(self,connection,record_id,vector,model_name="upstream",model_version="unverified"):
        values=[float(value) for value in vector]
        if not values or not all(isfinite(value) for value in values):
            raise ValueError("embedding must be a nonempty finite vector")
        connection.execute("INSERT INTO processed.ai08_embeddings(record_id,model_name,model_version,dimensions,embedding) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",(record_id,model_name,model_version,len(values),values))
        row=connection.execute("SELECT dimensions,embedding,model_name,model_version FROM processed.ai08_embeddings WHERE record_id=%s FOR UPDATE",(record_id,)).fetchone()
        if row["dimensions"]!=len(values) or row["embedding"]!=values or row["model_name"]!=model_name or row["model_version"]!=model_version:
            raise ValueError("record_id collision with different embedding")

    def save_embedding(self,record_id,vector,model_name="upstream",model_version="unverified"):
        with self._connect() as connection:
            self._save_embedding(connection,record_id,vector,model_name,model_version)

    def close(self):
        return None
