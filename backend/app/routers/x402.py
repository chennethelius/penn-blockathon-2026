"""x402 paid API endpoints — pay-per-call via USDT-TRC20."""

import os
from fastapi import APIRouter, Request, HTTPException
from app.services.tron import get_trc20_transfers

router = APIRouter()

TREASURY_ADDRESS = os.getenv("TRONTRUST_TREASURY_ADDRESS", "")

# Price table (in USDT, 6 decimal places)
PRICES = {
    "trust": 0.02,
    "token-check": 0.01,
    "reputation": 0.03,
    "token-forensics": 0.05,
    "register-passport": 1.00,
}


async def _verify_payment(tx_hash: str, expected_amount: float) -> bool:
    """Verify a USDT-TRC20 payment was made to treasury."""
    if not TREASURY_ADDRESS:
        return True  # Skip verification if no treasury set (dev mode)

    # TODO: verify tx_hash on TronGrid
    # - Confirm tx exists and is confirmed
    # - Confirm recipient is TREASURY_ADDRESS
    # - Confirm amount >= expected_amount
    # - Confirm it's USDT-TRC20 token
    return True  # Placeholder


def _payment_required_response(endpoint: str):
    """Return 402 Payment Required with payment instructions."""
    price = PRICES.get(endpoint, 0.01)
    return {
        "status": 402,
        "message": "Payment Required",
        "payTo": TREASURY_ADDRESS or "configure_treasury_address",
        "amount": price,
        "currency": "USDT-TRC20",
        "instructions": f"Send {price} USDT (TRC-20) to the payTo address, then retry with X-Payment header containing the tx hash.",
    }


@router.get("/trust")
async def x402_trust(address: str, request: Request):
    """Paid trust score lookup — 0.02 USDT."""
    payment_hash = request.headers.get("X-Payment")
    if not payment_hash:
        raise HTTPException(status_code=402, detail=_payment_required_response("trust"))

    if not await _verify_payment(payment_hash, PRICES["trust"]):
        raise HTTPException(status_code=402, detail={"error": "Payment verification failed"})

    # Reuse the free endpoint logic
    from app.routers.trust import _build_trust_profile
    profile = await _build_trust_profile(address)
    return profile


@router.get("/token-check")
async def x402_token_check(address: str, request: Request):
    """Paid token check — 0.01 USDT."""
    payment_hash = request.headers.get("X-Payment")
    if not payment_hash:
        raise HTTPException(status_code=402, detail=_payment_required_response("token-check"))

    if not await _verify_payment(payment_hash, PRICES["token-check"]):
        raise HTTPException(status_code=402, detail={"error": "Payment verification failed"})

    from app.routers.token import get_token_safety
    return await get_token_safety(address)


@router.get("/reputation")
async def x402_reputation(address: str, request: Request):
    """Paid reputation lookup — 0.03 USDT."""
    payment_hash = request.headers.get("X-Payment")
    if not payment_hash:
        raise HTTPException(status_code=402, detail=_payment_required_response("reputation"))

    if not await _verify_payment(payment_hash, PRICES["reputation"]):
        raise HTTPException(status_code=402, detail={"error": "Payment verification failed"})

    from app.routers.review import get_reviews
    return await get_reviews(address)


@router.post("/token-forensics")
async def x402_token_forensics(address: str, request: Request):
    """Paid deep token forensics — 0.05 USDT."""
    payment_hash = request.headers.get("X-Payment")
    if not payment_hash:
        raise HTTPException(status_code=402, detail=_payment_required_response("token-forensics"))

    if not await _verify_payment(payment_hash, PRICES["token-forensics"]):
        raise HTTPException(status_code=402, detail={"error": "Payment verification failed"})

    from app.routers.token import get_token_safety
    return await get_token_safety(address)


@router.post("/register-passport")
async def x402_register_passport(address: str, agentType: str, request: Request):
    """Paid passport registration — 1.00 USDT."""
    payment_hash = request.headers.get("X-Payment")
    if not payment_hash:
        raise HTTPException(status_code=402, detail=_payment_required_response("register-passport"))

    if not await _verify_payment(payment_hash, PRICES["register-passport"]):
        raise HTTPException(status_code=402, detail={"error": "Payment verification failed"})

    from app.routers.trust import register_agent
    from app.models.schemas import AgentRegisterRequest
    return await register_agent(AgentRegisterRequest(address=address, agentType=agentType))
