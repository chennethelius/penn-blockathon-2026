"""Token safety endpoints."""

from fastapi import APIRouter
from app.models.schemas import TokenResponse, Verdict
from app.services.tron import get_contract_info

router = APIRouter()


@router.get("/token/{address}", response_model=TokenResponse)
async def get_token_safety(address: str):
    """Check TRC-20 token safety."""
    try:
        contract = await get_contract_info(address)
        contract_data = contract.get("data", [{}])
        info = contract_data[0] if contract_data else {}
        bytecode = info.get("bytecode", "")

        # Heuristic checks on bytecode for known patterns
        freeze_function = "freeze" in bytecode.lower() if bytecode else False
        mint_function = "mint" in bytecode.lower() if bytecode else False

        # Simple risk heuristic
        risk = 0.2  # baseline
        if freeze_function:
            risk += 0.3
        if mint_function:
            risk += 0.15

        honeypot = risk > 0.6

        verdict = Verdict.TRUSTED
        if risk > 0.6:
            verdict = Verdict.AVOID
        elif risk > 0.4:
            verdict = Verdict.CAUTION
        elif risk > 0.2:
            verdict = Verdict.PROCEED

        return TokenResponse(
            address=address,
            honeypot=honeypot,
            liquidity=0.0,  # Requires SunSwap integration
            rugProbability=round(risk, 4),
            verdict=verdict,
            freezeFunction=freeze_function,
            mintFunction=mint_function,
        )

    except Exception:
        return TokenResponse(
            address=address,
            honeypot=False,
            liquidity=0.0,
            rugProbability=0.5,
            verdict=Verdict.CAUTION,
            freezeFunction=False,
            mintFunction=False,
        )
