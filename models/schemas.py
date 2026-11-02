"""Pydantic schemas for strict schema enforcement, structured output, and state validation."""

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class PillarItem(BaseModel):
    """Schema for an individual intelligence pillar item."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=300, description="Name of the model, tool, repo, or event")
    creator: str = Field(default="", max_length=200, description="Creating lab, author, or organization")
    summary: str = Field(..., min_length=5, max_length=2000, description="Precise summary of the update")
    source_url: str = Field(default="", max_length=1000, description="Direct URL citation or reference link")

    @field_validator("source_url")
    @classmethod
    def sanitize_and_validate_url(cls, v: str) -> str:
        if not v:
            return ""
        v = v.strip()
        # Basic sanity check: must start with http:// or https:// if provided
        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", v, re.IGNORECASE):
            # If invalid or relative, return empty or safe fallback
            return ""
        return v


class IntelligenceBrief(BaseModel):
    """Deterministic structured output schema for the daily AI & Tech Intelligence Brief."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date YYYY-MM-DD")
    top_headline: str = Field(..., min_length=5, max_length=500, description="Impactful top headline")
    highlights: List[str] = Field(..., min_length=1, max_length=10, description="Executive highlights")
    pillar_1: List[PillarItem] = Field(default_factory=list, description="New Model Launches & Research Breakthroughs")
    pillar_2: List[PillarItem] = Field(default_factory=list, description="Developer Tools, Frameworks & SDK Updates")
    pillar_3: List[PillarItem] = Field(default_factory=list, description="Major Tech & Industry Moves")
    pillar_4: List[PillarItem] = Field(default_factory=list, description="High-Level Practitioner & Thought Leader Insights")
    pillar_5: List[PillarItem] = Field(default_factory=list, description="Top Must-Try Repos / Tools")


class RecipientProfile(BaseModel):
    """Profile schema for briefing recipients."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    email: str = Field(..., min_length=3, max_length=254)
    name: str = Field(..., min_length=1, max_length=150)
    first_name: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=150)


class FetchHackerNewsInput(BaseModel):
    """Tool argument validation for Hacker News search."""
    model_config = ConfigDict(extra="forbid")

    lookback_hours: int = Field(default=24, ge=1, le=168, description="Hours of lookback (1 to 168)")
    keywords: Optional[List[str]] = Field(default=None, description="Keywords to query")


class FetchHuggingFaceInput(BaseModel):
    """Tool argument validation for Hugging Face daily papers."""
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=15, ge=1, le=50, description="Number of papers to retrieve")


class FetchGitHubTrendingInput(BaseModel):
    """Tool argument validation for GitHub Trending AI search."""
    model_config = ConfigDict(extra="forbid")

    days_back: int = Field(default=3, ge=1, le=30, description="Days to look back for repo creation")
    limit: int = Field(default=15, ge=1, le=50, description="Number of repositories to retrieve")


class TelemetryEvent(BaseModel):
    """Structured telemetry event schema."""
    model_config = ConfigDict(extra="ignore")

    trace_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_step: str
    tool_name: Optional[str] = None
    latency_ms: float = 0.0
    token_usage: Optional[Dict[str, int]] = None
    validation_status: str = "SUCCESS"  # SUCCESS, FAILED, RETRIED, SKIPPED
    details: Optional[Dict[str, Any]] = None


class CheckpointState(BaseModel):
    """Schema for resilient execution state checkpointing."""
    model_config = ConfigDict(extra="ignore")

    trace_id: str
    current_step: str = "INIT"
    completed_steps: List[str] = Field(default_factory=list)
    brief_data: Optional[Dict[str, Any]] = None
    generated_reports: Dict[str, str] = Field(default_factory=dict)
    dispatched_recipients: List[str] = Field(default_factory=list)
    failed_recipients: List[str] = Field(default_factory=list)
    idempotency_keys: Dict[str, str] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
