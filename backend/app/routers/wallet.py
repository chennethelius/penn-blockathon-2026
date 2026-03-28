"""TrustWallet endpoints — trust-gated smart account for AI agents."""

from fastapi import APIRouter
from pydantic import BaseModel
from app.services.contracts import get_contracts
from app.services import anubis_client

router = APIRouter()

DENY_FLAGS = {
    "wash_trading_detected",
    "circular_payments",
    "honeypot_risk",
    "energy_drain_attacker",
    "phishing_association",
    "address_poisoning",
}


class WalletSendRequest(BaseModel):
    to: str
    amountTrx: float


class SetMinTrustRequest(BaseModel):
    newScore: int


@router.post("/wallet/send")
async def wallet_send(req: WalletSendRequest):
    """Send TRX from the TrustWallet. Checks recipient trust on-chain before sending."""
    contracts = get_contracts()

    # 1. ML check on recipient via Anubis
    prediction = await anubis_client.predict_agent(req.to)
    risk_flags = set(prediction.get("risk_flags", []))
    blocked_flags = risk_flags & DENY_FLAGS

    if blocked_flags:
        return {
            "success": False,
            "error": f"Recipient blocked by ML risk check: {', '.join(blocked_flags)}",
            "recipientScore": prediction.get("ml_score"),
            "riskFlags": list(risk_flags),
            "txHash": "",
        }

    # 2. On-chain trust check (redundant but proves contract enforcement)
    check = contracts.wallet_check_recipient(req.to)

    if not check["wouldPass"]:
        return {
            "success": False,
            "error": f"Recipient trust score {check['score']} is below minimum {check['minRequired']}",
            "recipientScore": check["score"],
            "minRequired": check["minRequired"],
            "txHash": "",
        }

    # 3. Execute the send
    try:
        amount_sun = int(req.amountTrx * 1_000_000)
        tx_hash = contracts.wallet_send(req.to, amount_sun)
        return {
            "success": True,
            "txHash": tx_hash,
            "recipientScore": check["score"],
            "amountTrx": req.amountTrx,
            "to": req.to,
        }
    except Exception as e:
        error_msg = str(e)
        if "trust score too low" in error_msg.lower():
            return {
                "success": False,
                "error": f"Contract rejected: recipient trust score below threshold",
                "recipientScore": check["score"],
                "txHash": "",
            }
        return {
            "success": False,
            "error": f"Transaction failed: {e}",
            "txHash": "",
        }


@router.post("/wallet/set-min-trust")
async def set_min_trust(req: SetMinTrustRequest):
    """Update the minimum trust score required for outgoing transfers."""
    if req.newScore < 0 or req.newScore > 100:
        return {"success": False, "error": "Score must be 0-100"}

    contracts = get_contracts()
    try:
        tx_hash = contracts.wallet_set_min_trust(req.newScore)
        return {
            "success": True,
            "txHash": tx_hash,
            "newMinScore": req.newScore,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "txHash": ""}


@router.get("/wallet/check/{address}")
async def check_recipient(address: str):
    """Check if a recipient would pass the wallet's trust gate."""
    contracts = get_contracts()
    check = contracts.wallet_check_recipient(address)

    # Also get Anubis risk flags
    prediction = await anubis_client.predict_agent(address)
    risk_flags = prediction.get("risk_flags", [])
    blocked_flags = set(risk_flags) & DENY_FLAGS

    return {
        "address": address,
        "onChainScore": check["score"],
        "wouldPassContract": check["wouldPass"],
        "minRequired": check["minRequired"],
        "mlScore": prediction.get("ml_score"),
        "riskFlags": risk_flags,
        "blockedByML": len(blocked_flags) > 0,
        "blockedFlags": list(blocked_flags),
        "verdict": "APPROVED" if check["wouldPass"] and not blocked_flags else "BLOCKED",
    }


@router.get("/wallet/stats")
async def wallet_stats():
    """Get TrustWallet statistics."""
    contracts = get_contracts()
    stats = contracts.wallet_get_stats()
    return {
        "totalTransfers": stats["transfers"],
        "totalBlocked": stats["blocked"],
        "totalVolumeTrx": stats["volumeTrx"] / 1_000_000 if stats["volumeTrx"] > 0 else 0,
        "currentMinScore": stats["currentMinScore"],
        "trustEnforced": stats["enforcing"],
        "walletAddress": "TFD31Cr3PfZPZjPHUWSVstkZ53ZCEyX6yi",
    }


class LockAccountRequest(BaseModel):
    agentAddress: str


@router.post("/wallet/lock-permissions")
async def lock_account_permissions(req: LockAccountRequest):
    """Lock an agent's Tron account using native Account Permission Management.

    Sets the Active permission so the agent can ONLY interact through the
    TrustWallet contract. Protocol-level enforcement — even a compromised AI
    cannot bypass this. Uses Tron's native multi-sig, not a smart contract.
    """
    contracts = get_contracts()
    result = contracts.lock_account_to_trust_wallet(req.agentAddress)
    return result


@router.get("/wallet/permissions/{address}")
async def get_permissions(address: str):
    """Read current Tron account permissions. Shows owner, active, and
    any trust-gated restrictions applied via Account Permission Management."""
    contracts = get_contracts()
    return contracts.get_account_permissions(address)
