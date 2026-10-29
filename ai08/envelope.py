import hashlib
import json
from datetime import datetime,timezone
from .contracts import EventEnvelope,ModelIdentity

def stable_id(kind,subject,records,config_version):
    raw=json.dumps(["AI-08","analytics.signals.v1",kind,subject,sorted(r.record_id for r in records),config_version],ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def build_event(kind,subject,payload,records,config_version,confidence=0.0,model_name="AI08 rules"):
    records=sorted(records,key=lambda r:(r.t_start,r.record_id))
    first=records[0]
    return EventEnvelope(event_id=stable_id(kind,subject,records,config_version),schema="analytics.signals.v1",source_type=first.source_type,source_id=first.source_id,segment_id=first.segment_id,t_start=min(r.t_start for r in records),t_end=max(r.t_end for r in records),module="AI-08",model=ModelIdentity(name=model_name,version=config_version),language=first.language,confidence=max(0.0,min(1.0,float(confidence))),payload={"signal_type":kind,**payload},evidence_uri=first.evidence_uri,review_status="pending",created_at=datetime.now(timezone.utc).isoformat())
