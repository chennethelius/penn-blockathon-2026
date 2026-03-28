"""Token safety endpoints — wired to Anubis ML for deep analysis."""

from fastapi import APIRouter
from app.models.schemas import TokenResponse, Verdict
from app.services import anubis_client

router = APIRouter()


@router.get("/token/{address}", response_model=TokenResponse)
async def get_token_safety(address: str):
    """Check TRC-20 token safety via Anubis ML engine."""
    prediction = await anubis_client.predict_token(address)

    rug_prob = prediction.get("rug_probability") or 0.5
    token_specific = prediction.get("token_specific", {})

    honeypot = token_specific.get("honeypot_risk", False)
    freeze = token_specific.get("freeze_authority", False)
    mint = token_specific.get("mint_risk", False)

    if rug_prob > 0.6:
        verdict = Verdict.AVOID
    elif rug_prob > 0.4:
        verdict = Verdict.CAUTION
    elif rug_prob > 0.2:
        verdict = Verdict.PROCEED
    else:
        verdict = Verdict.TRUSTED

    return TokenResponse(
        address=address,
        honeypot=honeypot,
        liquidity=0.0,  # Would come from SunSwap indexing
        rugProbability=round(rug_prob, 4) if rug_prob else 0.5,
        verdict=verdict,
        freezeFunction=freeze,
        mintFunction=mint,
    )
