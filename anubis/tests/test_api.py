"""
API integration tests — uses FastAPI TestClient (no real TronGrid calls).
Feature vectors are injected directly to bypass live extraction.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

# We need the model trained before importing main
from models.trainer import train, MODEL_PATH
if not MODEL_PATH.exists():
    train(n_samples=5000)

# Patch TronGrid extractor so tests don't make real HTTP calls
import features.extractor as ext_module

DUMMY_ADDRESS = "T" + "a" * 33
DUMMY_FEATURES = {
    "wallet_age_days": 400.0,
    "justlend_repayment_rate": 0.92,
    "tx_count_total": 5000.0,
    "tx_count_30d": 200.0,
    "tx_count_7d": 50.0,
    "counterparty_avg_trust_score": 72.0,
    "token_holder_count": 1000.0,
    "token_age_days": 200.0,
}

RISKY_FEATURES = {
    "wallet_age_days": 5.0,
    "justlend_repayment_rate": 0.05,
    "honeypot_probability": 0.9,
    "energy_drain_victim_count": 50.0,
    "phishing_contract_association_score": 0.8,
    "counterparty_avg_trust_score": 12.0,
    "token_holder_count": 5.0,
    "token_age_days": 3.0,
}


@pytest.fixture(scope="module")
def client():
    from main import app
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["model_loaded"] is True
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Prediction — agent
# ---------------------------------------------------------------------------

def test_predict_trusted_agent(client):
    r = client.post("/predict/agent", json={
        "address": DUMMY_ADDRESS,
        "features": DUMMY_FEATURES,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["verdict"] in {"TRUSTED", "REPUTABLE"}
    assert data["ml_score"] >= 60


def test_predict_risky_agent(client):
    r = client.post("/predict/agent", json={
        "address": "T" + "b" * 33,
        "features": RISKY_FEATURES,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["verdict"] in {"RISKY", "BLACKLISTED", "CAUTION"}
    assert data["ml_score"] < 50
    assert "new_wallet" in data["risk_flags"]


def test_predict_invalid_address(client):
    r = client.post("/predict/agent", json={"address": "not_a_tron_address"})
    assert r.status_code == 422  # validation error


# ---------------------------------------------------------------------------
# Prediction — token
# ---------------------------------------------------------------------------

def test_predict_token(client):
    r = client.post("/predict/token", json={
        "token_address": DUMMY_ADDRESS,
        "features": DUMMY_FEATURES,
    })
    assert r.status_code == 200
    data = r.json()
    assert "token_specific" in data
    assert "honeypot_risk" in data["token_specific"]
    assert "audit_level" in data["token_specific"]


def test_predict_honeypot_token(client):
    r = client.post("/predict/token", json={
        "token_address": "T" + "c" * 33,
        "features": {**RISKY_FEATURES, "honeypot_probability": 0.95},
    })
    assert r.status_code == 200
    data = r.json()
    assert data["token_specific"]["honeypot_risk"] is True


# ---------------------------------------------------------------------------
# Full profile with Monte Carlo
# ---------------------------------------------------------------------------

def test_full_profile(client):
    features_json = json.dumps(DUMMY_FEATURES)
    r = client.get(f"/anubis/{DUMMY_ADDRESS}?features={features_json}")
    assert r.status_code == 200
    data = r.json()
    assert "prediction" in data
    assert "monte_carlo" in data
    assert data["monte_carlo"] is not None
    mc = data["monte_carlo"]
    assert mc["percentiles"]["p5"] <= mc["percentiles"]["p50"] <= mc["percentiles"]["p95"]
    assert mc["stability_rating"] in {"STABLE", "MODERATE", "VOLATILE"}


def test_full_profile_invalid_address(client):
    r = client.get("/anubis/bad_address")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------

def test_sentinel_alerts_empty(client):
    r = client.get("/sentinel/alerts?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert "alerts" in data
    assert "count" in data


def test_sentinel_invalid_severity(client):
    r = client.get("/sentinel/alerts?severity=invalid")
    assert r.status_code == 400


def test_threat_report(client):
    r = client.post("/threat/report", json={
        "malicious_address": "T" + "z" * 33,
        "threat_type": "energy_drain",
        "evidence": {"tx_hash": "abc123"},
        "reporter_address": "T" + "r" * 33,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["report_count"] == 1
    assert data["auto_blacklisted"] is False


def test_threat_report_auto_blacklist(client):
    addr = "T" + "x" * 33
    reporter_base = "T" + "y" * 33

    for i in range(3):
        r = client.post("/threat/report", json={
            "malicious_address": addr,
            "threat_type": "fake_usdt",
            "evidence": {},
            "reporter_address": reporter_base,
        })
        assert r.status_code == 200

    data = r.json()
    assert data["auto_blacklisted"] is True
    assert data["report_count"] == 3


# ---------------------------------------------------------------------------
# Risks summary
# ---------------------------------------------------------------------------

def test_risks_summary(client):
    r = client.get("/risks/summary")
    assert r.status_code == 200
    data = r.json()
    assert "total_alerts" in data
    assert "blacklisted_addresses" in data


# ---------------------------------------------------------------------------
# Features metadata
# ---------------------------------------------------------------------------

def test_features_endpoint(client):
    r = client.get("/features")
    assert r.status_code == 200
    data = r.json()
    assert data["feature_count"] == 50
    assert len(data["features"]) == 50
    groups = {f["group"] for f in data["features"]}
    assert groups == {"behavioral", "token_health", "network_threat"}
