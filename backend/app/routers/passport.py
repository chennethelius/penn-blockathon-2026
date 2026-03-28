"""Passport and KYA endpoints — reads from on-chain TrustPassport contract."""

from fastapi import APIRouter
from app.models.schemas import PassportResponse
from app.services.contracts import get_contracts

router = APIRouter()

# KYA code mapping (in-memory for demo, would be Supabase)
_kya_codes: dict[str, str] = {}


@router.get("/passport/{address}", response_model=PassportResponse)
async def get_passport(address: str):
    """Get full passport — reads from on-chain TrustPassport if deployed."""
    contracts = get_contracts()
    on_chain = contracts.get_passport(address)

    if on_chain.get("exists"):
        return PassportResponse(
            address=address,
            trustScore=on_chain["trustScore"],
            commercialScore=on_chain["commercialScore"],
            agentType=on_chain["agentType"],
            registeredAt=on_chain["registeredAt"],
            totalJobs=0,
            sunPoints=on_chain["sunPoints"],
            recentAttestations=[],
        )

    # Fallback: check Oracle for agent profile
    profile = contracts.get_agent_profile(address)
    if profile.get("exists"):
        trust = contracts.get_trust(address)
        return PassportResponse(
            address=address,
            trustScore=trust.get("score", 0),
            commercialScore=0,
            agentType=profile["agentType"],
            registeredAt=profile["registeredAt"],
            totalJobs=profile["totalJobs"],
            sunPoints=0,
            recentAttestations=[],
        )

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

    contracts = get_contracts()
    passport = contracts.get_passport(address)
    if passport.get("exists"):
        return {"address": address, **passport}
    return {"address": address, "status": "registered_no_passport"}
