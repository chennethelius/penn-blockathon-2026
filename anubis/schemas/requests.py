"""Pydantic request/response models for Anubis API."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class AgentPredictRequest(BaseModel):
    """POST /predict/agent — predict rug probability for an agent wallet."""
    address: str = Field(..., description="Tron wallet address (base58)")
    features: Optional[dict[str, float]] = Field(
        None,
        description="Pre-extracted feature dict. If omitted, features are fetched live from TronGrid.",
    )

    @field_validator("address")
    @classmethod
    def validate_tron_address(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("T") and len(v) == 34):
            raise ValueError(f"Invalid Tron address: {v!r}")
        return v


class TokenPredictRequest(BaseModel):
    """POST /predict/token — predict rug probability for a TRC-20 token."""
    token_address: str = Field(..., description="TRC-20 contract address")
    features: Optional[dict[str, float]] = None

    @field_validator("token_address")
    @classmethod
    def validate_tron_address(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("T") and len(v) == 34):
            raise ValueError(f"Invalid Tron address: {v!r}")
        return v


class ThreatReportRequest(BaseModel):
    """POST /threat/report — community threat report."""
    malicious_address: str
    threat_type: str = Field(
        ...,
        description="One of: energy_drain, fake_usdt, freeze_abuse, permission_bypass, sr_manipulation, address_poisoning",
    )
    evidence: dict[str, Any] = Field(default_factory=dict)
    reporter_address: str


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class BreakdownModel(BaseModel):
    behavioral: Optional[float]
    token_health: Optional[float]
    threat: Optional[float]
    community: Optional[float]


class DriverModel(BaseModel):
    feature: str
    value: float
    importance: float


class PredictionResponse(BaseModel):
    address: str
    rug_probability: Optional[float]
    ml_score: Optional[float]
    composite_score: Optional[float]
    verdict: str
    breakdown: BreakdownModel
    risk_flags: list[str]
    top_drivers: list[DriverModel]


class PercentilesModel(BaseModel):
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


class MonteCarloResponse(BaseModel):
    address: str
    n_simulations: int
    mean_score: float
    std_score: float
    percentiles: PercentilesModel
    stability_rating: str
    interpretation: str
    prediction: PredictionResponse


class AlertResponse(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    address: str
    description: str
    evidence: dict
    timestamp: float
    auto_blacklisted: bool


class ThreatSummaryResponse(BaseModel):
    total_alerts: int
    alerts_last_1h: int
    blacklisted_addresses: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    top_threat: Optional[str]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    sentinel_running: bool
    version: str = "anubis_v1"
