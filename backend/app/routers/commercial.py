"""Commercial trust endpoints (TronTrust exclusive)."""

from fastapi import APIRouter
from app.models.schemas import RecordPaymentRequest, TermsResponse

router = APIRouter()

# In-memory store for demo
_payments: list[dict] = []
_wallet_stats: dict[str, dict] = {}


@router.post("/commercial/record-payment")
async def record_payment(req: RecordPaymentRequest):
    """Record invoice payment — called by PayClaw after settlement."""
    _payments.append(req.model_dump())

    # Update wallet stats
    for addr in [req.payer, req.payee]:
        if addr not in _wallet_stats:
            _wallet_stats[addr] = {"total": 0, "paid": 0, "overdue": 0, "volume": 0.0}

    _wallet_stats[req.payer]["total"] += 1
    _wallet_stats[req.payer]["volume"] += req.amountUsdt
    if req.wasOverdue:
        _wallet_stats[req.payer]["overdue"] += 1
    else:
        _wallet_stats[req.payer]["paid"] += 1

    # TODO: call CommercialTrust.sol on-chain

    return {"status": "recorded", "invoiceId": req.invoiceId}


@router.get("/commercial/terms", response_model=TermsResponse)
async def get_terms(buyer: str, merchant: str):
    """Get recommended payment terms based on commercial trust score."""
    stats = _wallet_stats.get(buyer, {"total": 0, "paid": 0})

    if stats["total"] == 0:
        score = 50
    else:
        score = int((stats["paid"] / stats["total"]) * 100)

    if score >= 80:
        return TermsResponse(paymentWindowDays=30, requiresEscrow=False, creditLimitUsdt=100000.0, reasoning=f"Buyer score {score}: excellent payment history")
    elif score >= 60:
        return TermsResponse(paymentWindowDays=14, requiresEscrow=False, creditLimitUsdt=25000.0, reasoning=f"Buyer score {score}: good payment history")
    elif score >= 40:
        return TermsResponse(paymentWindowDays=7, requiresEscrow=True, creditLimitUsdt=5000.0, reasoning=f"Buyer score {score}: moderate risk, escrow recommended")
    else:
        return TermsResponse(paymentWindowDays=0, requiresEscrow=True, creditLimitUsdt=1000.0, reasoning=f"Buyer score {score}: high risk, prepay with escrow required")


@router.get("/commercial/relationship")
async def get_relationship(a: str, b: str):
    """Get commercial relationship between two addresses."""
    # Filter payments between these two addresses
    relevant = [p for p in _payments if {p["payer"], p["payee"]} == {a, b}]
    return {
        "partyA": a,
        "partyB": b,
        "invoicesTotal": len(relevant),
        "payments": relevant,
    }
