from math import isfinite
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .config import AI08Config

SourceType=Literal["tv","print","digital"]
Language=Literal["Urdu","English","Pashto","Roman Urdu"]

class EnrichedRecord(BaseModel):
    model_config=ConfigDict(extra="allow")
    record_id: str=Field(min_length=1)
    source_type: SourceType
    source_id: str=Field(min_length=1)
    segment_id: str|None=None
    channel: str|None=None
    outlet: str|None=None
    t_start: int=Field(ge=0)
    t_end: int=Field(ge=0)
    language: Language
    text: str=Field(min_length=1)
    entities: list[str]=Field(default_factory=list)
    tags: list[str]=Field(default_factory=list)
    keywords: list[str]=Field(default_factory=list)
    sentiment: float|None=Field(default=None,ge=-1,le=1)
    target_sentiment: dict[str,float]=Field(default_factory=dict)
    embedding: list[float]|None=None
    embedding_ref: str|None=None
    account_id: str|None=None
    evidence_uri: str|None=None

    @field_validator("embedding")
    @classmethod
    def valid_embedding(cls,value):
        if value is not None and (not value or any(not isfinite(v) for v in value)):
            raise ValueError("embedding must be a nonempty finite vector")
        return value

    @field_validator("target_sentiment")
    @classmethod
    def valid_targets(cls,value):
        if any(not isfinite(v) or v<-1 or v>1 for v in value.values()):
            raise ValueError("target sentiment must be between -1 and 1")
        return value

    @model_validator(mode="after")
    def check_times(self):
        if self.t_end<self.t_start:
            raise ValueError("t_end must not precede t_start")
        return self

class MentionCount(BaseModel):
    subject: str=Field(min_length=1)
    t_start: int=Field(ge=0)
    count: int=Field(ge=0)
    negative_count: int=Field(default=0,ge=0)

    @model_validator(mode="after")
    def check_counts(self):
        if self.negative_count>self.count:
            raise ValueError("negative_count exceeds count")
        return self

class ReferenceClaim(BaseModel):
    claim: str=Field(min_length=1)
    source_id: str=Field(min_length=1)
    evidence_uri: str=Field(min_length=1)
    refutes: list[str]=Field(default_factory=list)

class InferRequest(BaseModel):
    records: list[EnrichedRecord]=Field(min_length=1)
    mention_counts: list[MentionCount]=Field(default_factory=list)
    embedding_vectors: dict[str,list[float]]=Field(default_factory=dict)
    reference_claims: list[ReferenceClaim]=Field(default_factory=list)
    config: AI08Config=Field(default_factory=AI08Config)

    @model_validator(mode="after")
    def unique_records(self):
        ids=[r.record_id for r in self.records]
        if len(ids)!=len(set(ids)):
            raise ValueError("duplicate record_id")
        return self

class ModelIdentity(BaseModel):
    name: str
    version: str

class EventEnvelope(BaseModel):
    event_id: str
    schema_name: str=Field(alias="schema")
    source_type: SourceType
    source_id: str
    segment_id: str|None
    t_start: int
    t_end: int
    module: str
    model: ModelIdentity
    language: Language
    confidence: float=Field(ge=0,le=1)
    payload: dict[str,Any]
    evidence_uri: str|None
    review_status: Literal["pending","accepted","corrected","rejected"]
    created_at: str

class ReviewFeedback(BaseModel):
    event_id: str=Field(min_length=1)
    decision: Literal["accept","correct","reject"]
    reviewer: str=Field(min_length=1)
    time: int=Field(ge=0)
    corrected_value: dict[str,Any]|None=None

    @model_validator(mode="after")
    def check_correction(self):
        if self.decision=="correct" and self.corrected_value is None:
            raise ValueError("corrected_value required for correction")
        return self
