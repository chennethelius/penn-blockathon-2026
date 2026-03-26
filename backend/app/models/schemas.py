"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# --- Enums ---
class Verdict(str, Enum):
    TRUSTED = "trusted"
    PROCEED = "proceed"
    CAUTION = "caution"
    AVOID = "avoid"
    UNKNOWN = "unknown"


class Outcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    EXPIRED = "expired"


# --- Trust ---
class TrustResponse(BaseModel):
    address: str
    trustScore: int = Field(ge=0, le=100)
    verdict: Verdict
    riskOutlook: str
    tokenHealth: Optional[float] = None
    breakdown: dict
    flags: list[str] = []
    percentile: Optional[int] = None


class DeepTrustResponse(TrustResponse):
    monteCarlo: Optional[dict] = None
    riskFlags: list[str] = []
    tier: str = ""
    historicalScores: list[dict] = []


class AgentRegisterRequest(BaseModel):
    address: str
    agentType: str
    metadata: Optional[dict] = None


class AgentRegisterResponse(BaseModel):
    passportId: int
    initialScore: int = 50
    txHash: str


# --- Token ---
class TokenResponse(BaseModel):
    address: str
    honeypot: bool
    liquidity: float
    rugProbability: float
    verdict: Verdict
    freezeFunction: bool
    mintFunction: bool


# --- Review ---
class ReviewRequest(BaseModel):
    reviewerAddress: str
    targetAddress: str
    rating: int = Field(ge=1, le=10)
    comment: str


class ReviewVoteRequest(BaseModel):
    reviewId: str
    voterAddress: str
    vote: str  # "up" or "down"


class ReviewResponse(BaseModel):
    reviews: list[dict] = []
    avgRating: float
    sentiment: str
    reviewCount: int
    topReview: Optional[dict] = None


# --- Outcome ---
class OutcomeRequest(BaseModel):
    queryId: str
    outcome: Outcome
    reporter: str


# --- Commercial ---
class RecordPaymentRequest(BaseModel):
    payer: str
    payee: str
    amountUsdt: float
    daysToPayment: int
    invoiceId: str
    wasOverdue: bool


class TermsResponse(BaseModel):
    paymentWindowDays: int
    requiresEscrow: bool
    creditLimitUsdt: float
    reasoning: str


# --- Threat ---
class ThreatReportRequest(BaseModel):
    maliciousAddress: str
    threatType: str
    evidence: str
    reporterAddress: str


# --- Passport ---
class PassportResponse(BaseModel):
    address: str
    trustScore: int
    commercialScore: int
    agentType: str
    registeredAt: int
    totalJobs: int
    sunPoints: int
    recentAttestations: list[dict] = []


# --- Sun Points ---
class SunPointsResponse(BaseModel):
    address: str
    balance: int
    totalEarned: int
    streak: int
