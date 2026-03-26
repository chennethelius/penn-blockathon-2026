"""Core trust score endpoints — integrates Anubis ML + on-chain Oracle."""

from fastapi import APIRouter, Query
from app.models.schemas import (
    TrustResponse, DeepTrustResponse,
    AgentRegisterRequest, AgentRegisterResponse, Verdict,
)
from app.services import anubis_client
from app.services.contracts import get_contracts

router = APIRouter()

# Community review weight (Anubis handles the other 80%)
COMMUNITY_WEIGHT = 0.20
ANUBIS_WEIGHT = 0.80


def _verdict_from_anubis(verdict: str) -> Verdict:
    mapping = {
        "TRUSTED": Verdict.TRUSTED,
        "REPUTABLE": Verdict.PROCEED,
        "CAUTION": Verdict.CAUTION,
        "RISKY": Verdict.AVOID,
        "BLACKLISTED": Verdict.AVOID,
        "UNKNOWN": Verdict.CAUTION,
    }
    return mapping.get(verdict.upper(), Verdict.CAUTION)


def _risk_outlook(score: int) -> str:
    if score >= 80:
        return "stable"
    if score >= 60:
        return "moderate"
    if score >= 40:
        return "elevated"
    return "critical"


async def _build_trust_profile(address: str) -> dict:
    """Build trust profile: Anubis ML (80%) + community reviews (20%)."""
    # 1. Get ML prediction from Anubis
    prediction = await anubis_client.predict_agent(address)

    ml_score = prediction.get("ml_score") or 50.0
    breakdown = prediction.get("breakdown", {})

    # 2. Community reviews (placeholder — will come from Supabase)
    community_score = 50.0

    # 3. Composite: 80% Anubis + 20% community
    composite = int(ml_score * ANUBIS_WEIGHT + community_score * COMMUNITY_WEIGHT)
    composite = max(0, min(100, composite))

    verdict_str = prediction.get("verdict", "CAUTION")
    verdict = _verdict_from_anubis(verdict_str)

    # 4. Push score on-chain (fire and forget — don't block the response)
    contracts = get_contracts()
    if contracts.is_ready:
        try:
            contracts.update_score(address, composite, verdict_str)
        except Exception:
            pass  # On-chain write failure should never block API response

    return {
        "trustScore": composite,
        "verdict": verdict,
        "riskOutlook": _risk_outlook(composite),
        "breakdown": {
            "behavioral": breakdown.get("behavioral"),
            "tokenHealth": breakdown.get("token_health"),
            "threat": breakdown.get("threat"),
            "community": community_score,
        },
        "flags": prediction.get("risk_flags", []),
        "rugProbability": prediction.get("rug_probability"),
        "topDrivers": prediction.get("top_drivers", []),
    }


@router.get("/agent/{address}", response_model=TrustResponse)
async def get_agent_trust(address: str):
    """Get trust score for an agent wallet address."""
    profile = await _build_trust_profile(address)
    return TrustResponse(
        address=address,
        trustScore=profile["trustScore"],
        verdict=profile["verdict"],
        riskOutlook=profile["riskOutlook"],
        breakdown=profile["breakdown"],
        flags=profile["flags"],
    )


@router.get("/agent/{address}/deep", response_model=DeepTrustResponse)
async def get_agent_deep(address: str):
    """Deep trust analysis with Monte Carlo and risk flags."""
    # Full profile from Anubis (includes Monte Carlo)
    full = await anubis_client.get_full_profile(address)
    prediction = full.get("prediction", {})
    mc = full.get("monte_carlo")

    ml_score = prediction.get("ml_score") or 50.0
    community_score = 50.0
    composite = int(ml_score * ANUBIS_WEIGHT + community_score * COMMUNITY_WEIGHT)
    composite = max(0, min(100, composite))

    verdict_str = prediction.get("verdict", "CAUTION")
    breakdown = prediction.get("breakdown", {})

    # Determine tier from composite
    if composite >= 80:
        tier = "diamond"
    elif composite >= 60:
        tier = "gold"
    elif composite >= 40:
        tier = "silver"
    else:
        tier = "bronze"

    return DeepTrustResponse(
        address=address,
        trustScore=composite,
        verdict=_verdict_from_anubis(verdict_str),
        riskOutlook=_risk_outlook(composite),
        breakdown={
            "behavioral": breakdown.get("behavioral"),
            "tokenHealth": breakdown.get("token_health"),
            "threat": breakdown.get("threat"),
            "community": community_score,
        },
        flags=prediction.get("risk_flags", []),
        riskFlags=prediction.get("risk_flags", []),
        tier=tier,
        monteCarlo=mc,
        historicalScores=[],
    )


@router.get("/agents")
async def list_agents(sort: str = Query("trust"), limit: int = Query(50, le=100)):
    """Leaderboard of indexed agents."""
    # TODO: query from Supabase
    return {"agents": [], "total": 0, "sort": sort, "limit": limit}


@router.post("/agent/register", response_model=AgentRegisterResponse)
async def register_agent(req: AgentRegisterRequest):
    """Register a new agent — calls Oracle.registerAgent + mints Passport NFT."""
    contracts = get_contracts()

    if not contracts.is_ready:
        return AgentRegisterResponse(
            passportId=0,
            initialScore=50,
            txHash="contracts_not_deployed",
        )

    # 1. Register on Oracle
    oracle_tx = contracts.register_agent(req.address, req.agentType)

    # 2. Mint Passport NFT
    passport_tx = contracts.mint_passport(req.address, req.agentType)

    return AgentRegisterResponse(
        passportId=0,  # Would need to parse event logs for actual tokenId
        initialScore=50,
        txHash=oracle_tx or passport_tx or "",
    )
