"""Sun Points incentive system endpoints."""

import time
from fastapi import APIRouter
from app.models.schemas import SunPointsResponse

router = APIRouter()

# In-memory Sun Points store
_sunpoints: dict[str, dict] = {}


def _get_or_create(address: str) -> dict:
    if address not in _sunpoints:
        _sunpoints[address] = {
            "balance": 0,
            "totalEarned": 0,
            "streak": 0,
            "lastClaim": 0,
        }
    return _sunpoints[address]


def award_points(address: str, points: int):
    """Award Sun Points to an address (called internally)."""
    sp = _get_or_create(address)
    sp["balance"] += points
    sp["totalEarned"] += points


@router.get("/sunpoints", response_model=SunPointsResponse)
async def get_sunpoints(address: str):
    """Get Sun Points balance for an address."""
    sp = _get_or_create(address)
    return SunPointsResponse(
        address=address,
        balance=sp["balance"],
        totalEarned=sp["totalEarned"],
        streak=sp["streak"],
    )


@router.post("/sunpoints/claim")
async def claim_daily(address: str):
    """Claim daily Sun Points (+2)."""
    sp = _get_or_create(address)
    now = int(time.time())
    last = sp["lastClaim"]

    # One claim per 24h
    if now - last < 86400:
        remaining = 86400 - (now - last)
        return {"status": "already_claimed", "nextClaimInSeconds": remaining}

    sp["balance"] += 2
    sp["totalEarned"] += 2
    sp["lastClaim"] = now

    # Streak logic: if claimed within 48h of last claim, continue streak
    if last > 0 and now - last < 172800:
        sp["streak"] += 1
    else:
        sp["streak"] = 1

    return {
        "status": "claimed",
        "pointsEarned": 2,
        "newBalance": sp["balance"],
        "streak": sp["streak"],
    }
