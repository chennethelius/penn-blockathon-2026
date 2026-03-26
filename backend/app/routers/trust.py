"""Core trust score endpoints."""

from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import TrustResponse, DeepTrustResponse, AgentRegisterRequest, AgentRegisterResponse, Verdict
from app.services.tron import get_account_info, get_transactions, get_trc20_transfers

router = APIRouter()


def _compute_verdict(score: int) -> Verdict:
    if score >= 80:
        return Verdict.TRUSTED
    elif score >= 60:
        return Verdict.PROCEED
    elif score >= 40:
        return Verdict.CAUTION
    else:
        return Verdict.AVOID


def _compute_risk_outlook(score: int) -> str:
    if score >= 80:
        return "stable"
    elif score >= 60:
        return "moderate"
    elif score >= 40:
        return "elevated"
    else:
        return "critical"


async def _build_trust_profile(address: str) -> dict:
    """Build a trust profile from on-chain Tron data."""
    try:
        account = await get_account_info(address)
        txs = await get_transactions(address, limit=200)
        trc20 = await get_trc20_transfers(address, limit=200)
    except Exception:
        # If TronGrid is unreachable, return neutral score (never block)
        return {
            "trustScore": 50,
            "verdict": Verdict.CAUTION,
            "riskOutlook": "unknown",
            "breakdown": {"behavioral": 50, "tokenHealth": 50, "community": 50},
            "flags": ["trongrid_unreachable"],
        }

    # --- Behavioral scoring (50% weight) ---
    acc_data = account.get("data", [{}])
    acc = acc_data[0] if acc_data else {}

    tx_count = len(txs)
    trc20_count = len(trc20)
    balance_trx = acc.get("balance", 0) / 1_000_000  # sun to TRX

    # Simple heuristic scoring for demo
    behavioral = 50  # baseline
    if tx_count > 100:
        behavioral += 15
    elif tx_count > 20:
        behavioral += 8
    if balance_trx > 1000:
        behavioral += 10
    elif balance_trx > 100:
        behavioral += 5
    if trc20_count > 50:
        behavioral += 10
    # Wallet age signal from create_time
    create_time = acc.get("create_time", 0)
    if create_time > 0:
        import time
        age_days = (time.time() * 1000 - create_time) / (86400 * 1000)
        if age_days > 365:
            behavioral += 15
        elif age_days > 90:
            behavioral += 8
        elif age_days < 7:
            behavioral -= 10

    behavioral = max(0, min(100, behavioral))

    # Token health placeholder (30% weight) — will be replaced by Anubis
    token_health = 50

    # Community placeholder (20% weight) — will come from reviews DB
    community = 50

    # Composite: 50/30/20
    composite = int(behavioral * 0.5 + token_health * 0.3 + community * 0.2)
    composite = max(0, min(100, composite))

    flags = []
    if tx_count == 0:
        flags.append("no_transaction_history")
    if balance_trx < 1:
        flags.append("near_zero_balance")

    return {
        "trustScore": composite,
        "verdict": _compute_verdict(composite),
        "riskOutlook": _compute_risk_outlook(composite),
        "breakdown": {
            "behavioral": behavioral,
            "tokenHealth": token_health,
            "community": community,
        },
        "flags": flags,
        "txCount": tx_count,
        "trc20Count": trc20_count,
        "balanceTrx": balance_trx,
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
    profile = await _build_trust_profile(address)
    return DeepTrustResponse(
        address=address,
        trustScore=profile["trustScore"],
        verdict=profile["verdict"],
        riskOutlook=profile["riskOutlook"],
        breakdown=profile["breakdown"],
        flags=profile["flags"],
        riskFlags=profile["flags"],
        tier="standard",
        monteCarlo=None,  # Filled when Anubis is connected
        historicalScores=[],
    )


@router.get("/agents")
async def list_agents(sort: str = Query("trust"), limit: int = Query(50, le=100)):
    """Leaderboard of indexed agents. Placeholder until DB is wired."""
    return {"agents": [], "total": 0, "sort": sort, "limit": limit}


@router.post("/agent/register", response_model=AgentRegisterResponse)
async def register_agent(req: AgentRegisterRequest):
    """Register a new agent — calls Oracle + mints Passport on-chain."""
    # TODO: wire to actual contract calls via tronpy
    return AgentRegisterResponse(
        passportId=0,
        initialScore=50,
        txHash="pending_implementation",
    )
