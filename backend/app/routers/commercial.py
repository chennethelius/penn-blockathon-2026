"""Commercial trust endpoints — wired to CommercialTrust.sol on-chain."""

from fastapi import APIRouter
from app.models.schemas import RecordPaymentRequest, TermsResponse
from app.services.contracts import get_contracts

router = APIRouter()


@router.post("/commercial/record-payment")
async def record_payment(req: RecordPaymentRequest):
    """Record invoice payment — writes to CommercialTrust.sol on-chain."""
    contracts = get_contracts()

    tx_hash = ""
    if contracts.is_ready:
        try:
            # Convert USDT float to 6-decimal integer
            amount_usdt_int = int(req.amountUsdt * 1_000_000)
            tx_hash = contracts.record_payment(
                req.payer, req.payee, amount_usdt_int, req.daysToPayment, req.wasOverdue,
            )
        except Exception as e:
            tx_hash = f"error: {e}"

    return {"status": "recorded", "invoiceId": req.invoiceId, "txHash": tx_hash}


@router.get("/commercial/terms", response_model=TermsResponse)
async def get_terms(buyer: str, merchant: str):
    """Get recommended payment terms from on-chain CommercialTrust."""
    contracts = get_contracts()
    terms = contracts.get_recommended_terms(buyer, merchant)

    # Convert credit limit from 6-decimal USDT to float
    credit_limit = terms["creditLimitUsdt"] / 1_000_000 if terms["creditLimitUsdt"] > 1000 else terms["creditLimitUsdt"]

    score = contracts.get_commercial_score(buyer, merchant)
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
    score = contracts.get_commercial_score(a, b)
    terms = contracts.get_recommended_terms(a, b)

    return {
        "partyA": a,
        "partyB": b,
        "relationshipScore": score,
        "recommendedTerms": terms,
    }
