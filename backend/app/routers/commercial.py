"""Commercial trust endpoints — wired to CommercialTrust.sol on-chain."""

from fastapi import APIRouter
from app.models.schemas import RecordPaymentRequest, TermsResponse
from app.services.contracts import get_contracts

router = APIRouter()


@router.post("/commercial/record-payment")
async def record_payment(req: RecordPaymentRequest):
    """Record invoice payment — writes to CommercialTrust.sol on-chain."""
    contracts = get_contracts()

    if not contracts.is_ready:
        return {"success": False, "error": "Contracts not deployed", "invoiceId": req.invoiceId, "txHash": ""}

    try:
        amount_usdt_int = int(req.amountUsdt * 1_000_000)
        tx_hash = contracts.record_payment(
            req.payer, req.payee, amount_usdt_int, req.daysToPayment, req.wasOverdue,
        )
        return {"success": True, "invoiceId": req.invoiceId, "txHash": tx_hash}
    except Exception as e:
        return {"success": False, "error": f"On-chain write failed: {e}", "invoiceId": req.invoiceId, "txHash": ""}


@router.get("/commercial/terms", response_model=TermsResponse)
async def get_terms(buyer: str, merchant: str):
    """Get recommended payment terms from on-chain CommercialTrust."""
    contracts = get_contracts()
    try:
        terms = contracts.get_recommended_terms(buyer, merchant)
        credit_limit = terms["creditLimitUsdt"] / 1_000_000 if terms["creditLimitUsdt"] > 1000 else terms["creditLimitUsdt"]
        score = contracts.get_commercial_score(buyer, merchant)
    except Exception as e:
        return TermsResponse(
            paymentWindowDays=7,
            requiresEscrow=True,
            creditLimitUsdt=5000.0,
            reasoning=f"Could not read on-chain data ({e}). Default terms applied.",
        )
    return TermsResponse(
        paymentWindowDays=terms["paymentWindowDays"],
        requiresEscrow=terms["requiresEscrow"],
        creditLimitUsdt=credit_limit,
        reasoning=f"Buyer commercial score: {score}",
    )


@router.get("/commercial/relationship")
async def get_relationship(a: str, b: str):
    """Get commercial relationship between two addresses from on-chain."""
    contracts = get_contracts()
    try:
        score = contracts.get_commercial_score(a, b)
        terms = contracts.get_recommended_terms(a, b)
    except Exception:
        return {"partyA": a, "partyB": b, "relationshipScore": 50, "recommendedTerms": {"paymentWindowDays": 7, "requiresEscrow": True, "creditLimitUsdt": 5000}}
    return {
        "partyA": a,
        "partyB": b,
        "relationshipScore": score,
        "recommendedTerms": terms,
    }
