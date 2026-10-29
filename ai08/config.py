import hashlib
from pydantic import BaseModel, ConfigDict, Field

class AI08Config(BaseModel):
    model_config=ConfigDict(extra="forbid")
    version: str="development-unapproved"
    embedding_model_path: str|None=None
    topic_similarity: float=Field(default=0.72,ge=0,le=1)
    emerging_ratio: float=Field(default=1.5,ge=1)
    emerging_min_count: int=Field(default=3,ge=1)
    evolution_window_hours: int=Field(default=24,ge=1)
    evolution_step_hours: int=Field(default=6,ge=1)
    narrative_similarity: float=Field(default=0.85,ge=0,le=1)
    narrative_min_mentions: int=Field(default=2,ge=1)
    narrative_min_sources: int=Field(default=2,ge=1)
    baseline_min_observations: int=Field(default=4,ge=1)
    spike_z_threshold: float=Field(default=3.5,gt=0)
    spike_min_count: int=Field(default=3,ge=1)
    coordination_similarity: float=Field(default=0.85,ge=0,le=1)
    coordination_window_minutes: int=Field(default=15,ge=1)
    coordination_min_accounts: int=Field(default=3,ge=2)
    bias_deviation: float=Field(default=0.75,ge=0,le=2)
    contradiction_risk: float=Field(default=0.85,ge=0,le=1)
    corroboration_risk: float=Field(default=0.25,ge=0,le=1)
    coordination_risk: float=Field(default=0.20,ge=0,le=1)

    def signature(self):
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()[:16]
