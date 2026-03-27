"""Sentinel threat monitoring endpoints."""

from fastapi import APIRouter, Query

router = APIRouter()

# In-memory threat reports for demo
_threat_reports: dict[str, list[dict]] = {}
_blacklisted: set[str] = set()

THREAT_TYPES = [
    "energy_drain",
    "fake_usdt",
    "freeze_abuse",
    "permission_bypass",
    "sr_manipulation",
    "address_poisoning",
]


@router.get("/sentinel/alerts")
async def get_alerts(severity: str = Query("all"), limit: int = Query(10, le=100)):
    """Get real-time sentinel alerts."""
    # TODO: wire to Anubis sentinel engine
    return {"alerts": [], "severity": severity, "limit": limit}


@router.get("/monitor/alerts")
async def get_monitor_alerts():
    """Get monitoring alerts (alias for sentinel)."""
    return {"alerts": [], "totalThreats": len(_blacklisted)}


@router.post("/threat/report")
async def report_threat(maliciousAddress: str, threatType: str, evidence: str, reporterAddress: str):
    """Report a malicious address. 3+ independent reports triggers auto-blacklist."""
    if threatType not in THREAT_TYPES:
        return {"error": f"Invalid threat type. Must be one of: {THREAT_TYPES}"}

    report = {
        "reporter": reporterAddress,
        "threatType": threatType,
        "evidence": evidence,
    }

    if maliciousAddress not in _threat_reports:
        _threat_reports[maliciousAddress] = []

    # Check for duplicate reporter
    existing_reporters = {r["reporter"] for r in _threat_reports[maliciousAddress]}
    if reporterAddress in existing_reporters:
        return {"status": "duplicate", "message": "Already reported by this address"}

    _threat_reports[maliciousAddress].append(report)

    # Auto-blacklist after 3 independent reports
    report_count = len(_threat_reports[maliciousAddress])
    auto_blacklisted = False
    if report_count >= 3 and maliciousAddress not in _blacklisted:
        _blacklisted.add(maliciousAddress)
        auto_blacklisted = True
        # TODO: call TronTrustOracle.blacklist() on-chain

    return {
        "status": "reported",
        "reportCount": report_count,
        "autoBlacklisted": auto_blacklisted,
        "sunPointsEarned": 5,
    }
