"""Sentinel threat monitoring endpoints — wired to Anubis + on-chain Oracle."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services import anubis_client
from app.services.contracts import get_contracts

router = APIRouter()

THREAT_TYPES = [
    "energy_drain",
    "fake_usdt",
    "freeze_abuse",
    "permission_bypass",
    "sr_manipulation",
    "address_poisoning",
]

# In-memory report tracking (for auto-blacklist logic in the gateway)
_threat_reports: dict[str, list[dict]] = {}
_blacklisted: set[str] = set()


class ThreatReportBody(BaseModel):
    maliciousAddress: str
    threatType: str
    evidence: str
    reporterAddress: str


@router.get("/sentinel/alerts")
async def get_alerts(severity: str = Query("all"), limit: int = Query(10, le=100)):
    """Get real-time sentinel alerts from Anubis."""
    sev = severity if severity != "all" else None
    alerts = await anubis_client.get_sentinel_alerts(severity=sev, limit=limit)
    return {"alerts": alerts, "severity": severity, "limit": limit}


@router.get("/monitor/alerts")
async def get_monitor_alerts():
    """Monitoring alerts summary."""
    alerts = await anubis_client.get_sentinel_alerts(limit=100)
    return {"alerts": alerts, "totalThreats": len(_blacklisted)}


@router.post("/threat/report")
async def report_threat(body: ThreatReportBody):
    """Report a malicious address. 3+ independent reports triggers auto-blacklist on-chain."""
    if body.threatType not in THREAT_TYPES:
        return {"error": f"Invalid threat type. Must be one of: {THREAT_TYPES}"}

    report = {
        "reporter": body.reporterAddress,
        "threatType": body.threatType,
        "evidence": body.evidence,
    }

    if body.maliciousAddress not in _threat_reports:
        _threat_reports[body.maliciousAddress] = []

    # Deduplicate by reporter
    existing_reporters = {r["reporter"] for r in _threat_reports[body.maliciousAddress]}
    if body.reporterAddress in existing_reporters:
        return {"status": "duplicate", "message": "Already reported by this address"}

    _threat_reports[body.maliciousAddress].append(report)
    report_count = len(_threat_reports[body.maliciousAddress])

    # Auto-blacklist after 3 independent reports → push to Oracle on-chain
    auto_blacklisted = False
    if report_count >= 3 and body.maliciousAddress not in _blacklisted:
        _blacklisted.add(body.maliciousAddress)
        auto_blacklisted = True

        contracts = get_contracts()
        if contracts.is_ready:
            try:
                contracts.blacklist_agent(
                    body.maliciousAddress,
                    f"Auto-blacklisted: {report_count} reports ({body.threatType})",
                )
            except Exception:
                pass  # Don't fail the API response

    return {
        "status": "reported",
        "reportCount": report_count,
        "autoBlacklisted": auto_blacklisted,
        "sunPointsEarned": 5,
    }
