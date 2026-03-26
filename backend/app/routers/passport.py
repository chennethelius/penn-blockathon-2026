"""Passport and KYA endpoints."""

from fastapi import APIRouter
from app.models.schemas import PassportResponse

router = APIRouter()

# In-memory passport store for demo
_passports: dict[str, dict] = {}
_kya_codes: dict[str, str] = {}  # code -> address


@router.get("/passport/{address}", response_model=PassportResponse)
async def get_passport(address: str):
    """Get full passport for an address."""
    if address in _passports:
        return PassportResponse(**_passports[address])

    # Return default for unregistered
    return PassportResponse(
        address=address,
        trustScore=0,
        commercialScore=0,
        agentType="unregistered",
        registeredAt=0,
        totalJobs=0,
        sunPoints=0,
        recentAttestations=[],
    )


@router.get("/kya/{code}")
async def kya_lookup(code: str):
    """Know Your Agent lookup by short code."""
    address = _kya_codes.get(code)
    if not address:
        return {"error": "KYA code not found"}

    if address in _passports:
        return _passports[address]
    return {"address": address, "status": "registered_no_passport"}
