"""
Anubis ML Risk Engine — FastAPI Service
========================================
TronTrust's Wadjet equivalent: XGBoost rug prediction, Monte Carlo simulation,
and Sentinel real-time threat monitoring.

Endpoints:
  POST /predict/agent          — rug probability for agent wallet
  POST /predict/token          — rug probability for TRC-20 token
  GET  /anubis/{address}       — full risk profile + Monte Carlo
  GET  /sentinel/alerts        — real-time monitoring alerts
  GET  /risks/summary          — threat landscape dashboard
  GET  /health                 — service health
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from engine.predictor import AnubisPredictor
from engine.monte_carlo import MonteCarloSimulator
from engine.sentinel import Sentinel, AlertType, AlertSeverity
from features.extractor import TronFeatureExtractor
from features.schema import AgentFeatureVector, AGENT_FEATURES
from schemas.requests import (
    AgentPredictRequest,
    TokenPredictRequest,
    ThreatReportRequest,
    MonteCarloResponse,
    AlertResponse,
    ThreatSummaryResponse,
    HealthResponse,
)

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("anubis")

# ---------------------------------------------------------------------------
# Global service instances (initialised in lifespan)
# ---------------------------------------------------------------------------
_predictor: Optional[AnubisPredictor] = None
_simulator: Optional[MonteCarloSimulator] = None
_sentinel: Optional[Sentinel] = None
_extractor: Optional[TronFeatureExtractor] = None
_rng = np.random.default_rng()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _predictor, _simulator, _sentinel, _extractor

    logger.info("Anubis starting up...")

    # Extractor
    _extractor = TronFeatureExtractor(
        trongrid_base=os.getenv("TRONGRID_BASE_URL", "https://api.trongrid.io"),
        api_key=os.getenv("TRONGRID_API_KEY", ""),
        tronscan_api_key=os.getenv("TRONSCAN_API_KEY", ""),
    )

    # Model
    model_path = Path(os.getenv("MODEL_PATH", "models/anubis_v1.json"))
    _predictor = AnubisPredictor(model_path)

    if not _predictor.is_ready:
        logger.warning(
            "Model not found — run `python -m models.trainer` to train it. "
            "Predictions will return UNKNOWN until the model is loaded."
        )

    # Monte Carlo (needs the internal XGBoost model object)
    if _predictor.is_ready:
        _simulator = MonteCarloSimulator(_predictor._model)

    # Sentinel
    _sentinel = Sentinel(
        trongrid_base=os.getenv("TRONGRID_BASE_URL", "https://api.trongrid.io"),
        api_key=os.getenv("TRONGRID_API_KEY", ""),
        check_interval=float(os.getenv("SENTINEL_CHECK_INTERVAL_SECONDS", "30")),
    )
    await _sentinel.start()

    logger.info("Anubis ready. Model loaded: %s", _predictor.is_ready)

    yield

    # Shutdown
    logger.info("Anubis shutting down...")
    await _sentinel.stop()
    await _extractor.close()


app = FastAPI(
    title="Anubis ML Risk Engine",
    description="TronTrust's ML risk scoring service. XGBoost rug prediction, Monte Carlo confidence intervals, Sentinel real-time threat monitoring.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper: build feature vector from request
# ---------------------------------------------------------------------------

async def _build_fv(address: str, features: Optional[dict], is_token: bool = False) -> AgentFeatureVector:
    """
    If features dict is provided (e.g. from a test or cached data), use it.
    Otherwise extract live from TronGrid/TronScan.
    """
    if features:
        fv = AgentFeatureVector(address=address)
        for name, val in features.items():
            if name in AGENT_FEATURES:
                setattr(fv, name, float(val))
        fv.clamp()
        return fv
    elif is_token:
        return await _extractor.extract_token(address)
    else:
        return await _extractor.extract(address)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/predict/agent", tags=["Prediction"])
async def predict_agent(req: AgentPredictRequest):
    """
    Predict rug probability for an agent wallet.
    Returns trust score, verdict, breakdown, risk flags, and top feature drivers.
    """
    fv = await _build_fv(req.address, req.features)
    result = _predictor.predict(fv)
    return result


@app.post("/predict/token", tags=["Prediction"])
async def predict_token(req: TokenPredictRequest):
    """
    Predict rug probability for a TRC-20 token contract.
    Focuses on token health features (liquidity, holder concentration, honeypot signals).
    """
    fv = await _build_fv(req.token_address, req.features, is_token=True)
    result = _predictor.predict(fv)

    # Enrich with token-specific interpretation
    result["token_specific"] = {
        "honeypot_risk": fv.honeypot_probability > 0.5,
        "freeze_authority": bool(fv.freeze_function_present),
        "mint_risk": bool(fv.mint_function_present) and not bool(fv.owner_renounced),
        "concentrated_ownership": fv.top10_holder_concentration > 0.8,
        "audit_level": ["none", "community", "professional"][int(fv.audit_score)],
    }
    return result


@app.get("/anubis/{address}", tags=["Full Profile"])
async def get_full_profile(
    address: str,
    features: Optional[str] = Query(None, description="JSON-encoded feature overrides"),
):
    """
    Full risk profile for an address including:
    - Trust score and verdict
    - ML score breakdown
    - Monte Carlo confidence intervals (10K simulations)
    - Risk flags
    - Top feature drivers
    - Sentinel alert history for this address
    """
    if not (address.startswith("T") and len(address) == 34):
        raise HTTPException(400, "Invalid Tron address")

    # Parse optional feature overrides
    feat_dict = None
    if features:
        import json
        try:
            feat_dict = json.loads(features)
        except ValueError:
            raise HTTPException(400, "features must be valid JSON")

    fv = await _build_fv(address, feat_dict)
    prediction = _predictor.predict(fv)

    # Monte Carlo
    mc_result = None
    if _simulator and _predictor.is_ready:
        mc = _simulator.simulate(fv, rng=_rng)
        mc_result = mc.to_dict()

    # Address-specific sentinel alerts
    address_alerts = [
        a for a in _sentinel.get_alerts(limit=1000)
        if a["address"] == address
    ]

    return {
        "address": address,
        "prediction": prediction,
        "monte_carlo": mc_result,
        "sentinel_alerts": address_alerts[:10],
        "is_blacklisted": _sentinel.is_blacklisted(address),
        "generated_at": time.time(),
    }


@app.get("/sentinel/alerts", tags=["Sentinel"])
async def get_sentinel_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: low|medium|high|critical"),
    alert_type: Optional[str] = Query(None, description="Filter by type: energy_drain|fake_usdt|freeze_abuse|permission_bypass|sr_manipulation|address_poisoning"),
    limit: int = Query(50, ge=1, le=500),
    since: Optional[float] = Query(None, description="Unix timestamp — only return alerts after this time"),
):
    """
    Real-time Sentinel monitoring alerts.
    Tron-native threat detection: energy drain, fake USDT, freeze abuse,
    permission bypass, SR manipulation, address poisoning.
    """
    sev = None
    if severity:
        try:
            sev = AlertSeverity(severity)
        except ValueError:
            raise HTTPException(400, f"Invalid severity: {severity}")

    atype = None
    if alert_type:
        try:
            atype = AlertType(alert_type)
        except ValueError:
            raise HTTPException(400, f"Invalid alert_type: {alert_type}")

    alerts = _sentinel.get_alerts(severity=sev, alert_type=atype, limit=limit, since=since)
    return {"alerts": alerts, "count": len(alerts)}


@app.get("/risks/summary", tags=["Sentinel"])
async def get_risks_summary():
    """
    Dashboard summary of current Tron threat landscape.
    Total alerts, blacklisted addresses, breakdown by type and severity.
    """
    return _sentinel.get_threat_summary()


@app.post("/threat/report", tags=["Sentinel"])
async def report_threat(req: ThreatReportRequest):
    """
    Community threat report. After 3 independent reports on the same address,
    it is auto-blacklisted and all TronTrust Guard users are alerted.
    """
    result = _sentinel.record_report(
        address=req.malicious_address,
        threat_type=req.threat_type,
        reporter=req.reporter_address,
    )

    if result["auto_blacklisted"]:
        # Also trigger a score=0 update via the oracle (hook for API gateway)
        logger.warning(
            "Address %s auto-blacklisted — notify oracle to set score=0",
            req.malicious_address,
        )

    return result


@app.get("/health", tags=["Meta"])
async def health():
    """Service health check."""
    return HealthResponse(
        status="ok" if _predictor and _predictor.is_ready else "degraded",
        model_loaded=bool(_predictor and _predictor.is_ready),
        sentinel_running=bool(_sentinel and _sentinel._running),
    )


@app.get("/features", tags=["Meta"])
async def list_features():
    """Return the canonical 50-feature list with importance scores."""
    fi = _predictor.get_feature_importances() if _predictor else {}
    return {
        "feature_count": len(AGENT_FEATURES),
        "features": [
            {
                "index": i,
                "name": name,
                "importance": fi.get(name, None),
                "group": (
                    "behavioral" if i < 25
                    else "token_health" if i < 40
                    else "network_threat"
                ),
            }
            for i, name in enumerate(AGENT_FEATURES)
        ],
    }


@app.get("/", include_in_schema=False)
async def root():
    return {"service": "Anubis ML Risk Engine", "version": "1.0.0", "docs": "/docs"}
