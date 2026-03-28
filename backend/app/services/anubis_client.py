"""HTTP client for the Anubis ML engine service."""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

ANUBIS_URL = os.getenv("ANUBIS_URL", "http://localhost:8001")
TIMEOUT = 10.0


async def predict_agent(address: str, features: dict = None) -> dict:
    """Call Anubis POST /predict/agent and return the full prediction."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {"address": address}
            if features:
                payload["features"] = features
            resp = await client.post(f"{ANUBIS_URL}/predict/agent", json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Anubis predict_agent failed for %s: %s", address, e)
        return _fallback(address)


async def predict_token(token_address: str, features: dict = None) -> dict:
    """Call Anubis POST /predict/token."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {"token_address": token_address}
            if features:
                payload["features"] = features
            resp = await client.post(f"{ANUBIS_URL}/predict/token", json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Anubis predict_token failed for %s: %s", token_address, e)
        return _fallback(token_address)


async def get_full_profile(address: str) -> dict:
    """Call Anubis GET /anubis/{address} for full profile + Monte Carlo."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{ANUBIS_URL}/anubis/{address}")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Anubis full profile failed for %s: %s", address, e)
        return {"prediction": _fallback(address), "monte_carlo": None, "sentinel_alerts": []}


async def get_sentinel_alerts(severity: str = None, limit: int = 50) -> list:
    """Call Anubis GET /sentinel/alerts."""
    try:
        params = {"limit": limit}
        if severity:
            params["severity"] = severity
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{ANUBIS_URL}/sentinel/alerts", params=params)
            resp.raise_for_status()
            return resp.json().get("alerts", [])
    except Exception as e:
        logger.warning("Anubis sentinel alerts failed: %s", e)
        return []


async def health_check() -> dict:
    """Check if Anubis service is healthy."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ANUBIS_URL}/health")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {"status": "unreachable", "model_loaded": False, "sentinel_running": False}


def _fallback(address: str) -> dict:
    """Fallback when Anubis is unreachable — return neutral score, never block."""
    return {
        "address": address,
        "rug_probability": None,
        "ml_score": 50.0,
        "composite_score": 50.0,
        "verdict": "CAUTION",
        "breakdown": {"behavioral": None, "token_health": None, "threat": None, "community": None},
        "risk_flags": ["anubis_unreachable"],
        "top_drivers": [],
    }
