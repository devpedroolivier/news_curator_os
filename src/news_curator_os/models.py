from enum import Enum

from pydantic import BaseModel, Field


class StageState(str, Enum):
    completed = "completed"
    attention = "attention"


class StageCard(BaseModel):
    key: str
    title: str
    state: StageState
    summary: str
    details: list[str] = Field(default_factory=list)
    score: int | None = None


class SearchEvidence(BaseModel):
    title: str
    source: str
    url: str | None = None
    source_domain: str | None = None
    source_type: str = "news"
    is_official: bool = False
    published_at: str | None = None
    description: str | None = None
    query: str | None = None
    relevance_score: int | None = None


class SearchExecution(BaseModel):
    provider: str
    mode: str
    primary_query: str
    query_plan: list[str] = Field(default_factory=list)
    total_results: int = 0
    evidence: list[SearchEvidence] = Field(default_factory=list)
    unique_source_count: int = 0
    official_source_count: int = 0
    note: str | None = None


class AnalysisPayload(BaseModel):
    summary: str
    entities: list[str] = Field(default_factory=list)
    key_claims: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    score: int = 0


class VerificationPayload(BaseModel):
    summary: str
    corroborated_points: list[str] = Field(default_factory=list)
    conflicting_points: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    official_source_points: list[str] = Field(default_factory=list)
    source_consensus: str = ""
    divergence_detected: bool = False
    score: int = 0


class QualificationOutput(BaseModel):
    editorial_verdict: str
    credibility_band: str
    misinformation_risk: str
    recommended_action: str
    confidence_score: int = 0


class AuditEntry(BaseModel):
    stage: str
    severity: str
    message: str
    created_at: str


class PipelineRun(BaseModel):
    run_id: str
    created_at: str
    headline: str
    normalized_headline: str
    execution_mode: str
    llm_mode: str
    search_provider: str
    stages: list[StageCard]
    evidence: list[SearchEvidence] = Field(default_factory=list)
    output: QualificationOutput
    article_markdown: str = ""
    next_actions: list[str] = Field(default_factory=list)
    audit: list[AuditEntry] = Field(default_factory=list)


class RecentRunSummary(BaseModel):
    run_id: str
    created_at: str
    headline: str
    credibility_band: str
    confidence_score: int
    evidence_count: int
    execution_mode: str
    llm_mode: str


class MonitoringSummary(BaseModel):
    status: str
    database_ready: bool
    total_runs: int
    runs_with_evidence: int
    degraded_runs: int
    latest_run_at: str | None = None
    search_provider: str
    openai_enabled: bool


class HeadlineRequest(BaseModel):
    headline: str = Field(min_length=8, max_length=280)
