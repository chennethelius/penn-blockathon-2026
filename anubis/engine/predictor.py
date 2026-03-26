"""
Anubis Predictor
================
Loads the trained XGBoost model and converts raw rug probability (0-1)
into the 0-100 TronTrust score plus a human-readable verdict.

Score = 1 - rug_probability, scaled to [0, 100]
Weighting respects the 50/30/20 split mandated by the spec:
  50% on-chain behavioral (XGBoost features 0-24)
  30% ML token health (features 25-39)
  20% community reviews (injected externally, not from this module)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import xgboost as xgb

from features.schema import AgentFeatureVector, AGENT_FEATURES, FEATURE_IDX

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "models" / "anubis_v1.json"
META_PATH  = Path(__file__).parent.parent / "models" / "anubis_v1_meta.json"

# Verdict thresholds
VERDICT_BANDS = [
    (80, "TRUSTED"),
    (60, "REPUTABLE"),
    (40, "CAUTION"),
    (20, "RISKY"),
    (0,  "BLACKLISTED"),
]

# Sub-score feature slices (canonical indices)
BEHAVIORAL_SLICE  = slice(0, 25)
TOKEN_HEALTH_SLICE = slice(25, 40)
THREAT_SLICE       = slice(40, 50)


def _verdict(score: float) -> str:
    for threshold, label in VERDICT_BANDS:
        if score >= threshold:
            return label
    return "BLACKLISTED"


class AnubisPredictor:
    """
    Thread-safe (read-only after load) XGBoost predictor.
    """

    def __init__(self, model_path: Path = MODEL_PATH):
        self._model = xgb.XGBClassifier()
        if not model_path.exists():
            logger.warning(
                "Model not found at %s — run `python -m models.trainer` first",
                model_path,
            )
            self._ready = False
        else:
            self._model.load_model(str(model_path))
            self._ready = True
            logger.info("Anubis model loaded from %s", model_path)

        # Load feature importance metadata
        self._fi: dict[str, float] = {}
        if META_PATH.exists():
            meta = json.loads(META_PATH.read_text())
            self._fi = meta.get("feature_importances", {})

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Core prediction
    # ------------------------------------------------------------------

    def predict(self, fv: AgentFeatureVector) -> dict:
        """
        Full prediction for one feature vector.
        Returns a rich dict consumed by the API layer.
        """
        x = fv.to_numpy().reshape(1, -1)

        if not self._ready:
            return self._fallback(fv.address)

        # Raw rug probability from XGBoost
        rug_prob = float(self._model.predict_proba(x)[0, 1])

        # Convert to trust score 0-100
        ml_score = (1.0 - rug_prob) * 100.0

        # Sub-scores: re-run model on masked feature sets
        behavioral_score  = self._sub_score(x, BEHAVIORAL_SLICE)
        token_health_score = self._sub_score(x, TOKEN_HEALTH_SLICE)
        threat_score       = self._sub_score(x, THREAT_SLICE)

        # Composite (community reviews injected by API layer, default 50)
        # 50% behavioral + 30% token health + 20% community (placeholder)
        composite_ml = 0.50 * behavioral_score + 0.30 * token_health_score + 0.20 * 50.0

        verdict = _verdict(ml_score)
        risk_flags = self._compute_flags(fv)

        return {
            "address": fv.address,
            "rug_probability": round(rug_prob, 4),
            "ml_score": round(ml_score, 2),
            "composite_score": round(composite_ml, 2),  # before community injection
            "verdict": verdict,
            "breakdown": {
                "behavioral": round(behavioral_score, 2),
                "token_health": round(token_health_score, 2),
                "threat": round(threat_score, 2),
                "community": None,  # filled by API layer
            },
            "risk_flags": risk_flags,
            "feature_vector": fv.to_dict(),
            "top_drivers": self._top_drivers(x[0]),
        }

    def predict_batch(self, fvs: list[AgentFeatureVector]) -> list[dict]:
        if not self._ready:
            return [self._fallback(fv.address) for fv in fvs]

        X = np.vstack([fv.to_numpy() for fv in fvs])
        probs = self._model.predict_proba(X)[:, 1]

        return [
            {
                **self.predict(fv),
                "rug_probability": float(p),
                "ml_score": round((1.0 - float(p)) * 100, 2),
                "verdict": _verdict((1.0 - float(p)) * 100),
            }
            for fv, p in zip(fvs, probs)
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sub_score(self, x: np.ndarray, feature_slice: slice) -> float:
        """
        Score using only features in the given slice; zero out the rest.
        Returns 0-100 score for that dimension.
        """
        x_masked = x.copy()
        x_masked[0, :feature_slice.start] = 0.0
        x_masked[0, feature_slice.stop:] = 0.0
        try:
            p = float(self._model.predict_proba(x_masked)[0, 1])
            return (1.0 - p) * 100.0
        except Exception:
            return 50.0

    def _top_drivers(self, x: np.ndarray, top_n: int = 5) -> list[dict]:
        """
        Return the top-N features driving the risk score,
        weighted by feature importance × feature value contribution.
        """
        if not self._fi:
            return []
        drivers = []
        for name in AGENT_FEATURES:
            fi_weight = self._fi.get(name, 0.0)
            val = float(x[FEATURE_IDX[name]])
            # Higher importance + higher value for threat features → higher risk
            drivers.append({"feature": name, "value": round(val, 4), "importance": round(fi_weight, 4)})

        return sorted(drivers, key=lambda d: -d["importance"])[:top_n]

    def _compute_flags(self, fv: AgentFeatureVector) -> list[str]:
        flags = []
        if fv.wallet_age_days < 30:
            flags.append("new_wallet")
        if fv.justlend_repayment_rate < 0.5 and fv.justlend_total_borrowed_usdt > 0:
            flags.append("poor_repayment_history")
        if fv.sunswap_wash_trading_score > 0.5:
            flags.append("wash_trading_detected")
        if fv.honeypot_probability > 0.6:
            flags.append("honeypot_risk")
        if fv.freeze_function_present and not fv.owner_renounced:
            flags.append("freeze_authority_active")
        if fv.energy_drain_victim_count > 5:
            flags.append("energy_drain_attacker")
        if fv.phishing_contract_association_score > 0.5:
            flags.append("phishing_association")
        if fv.address_poisoning_attempts > 10:
            flags.append("address_poisoning")
        if fv.mixer_interaction_score > 0.4:
            flags.append("mixer_usage")
        if fv.circular_payment_ratio > 0.6:
            flags.append("circular_payments")
        if fv.top10_holder_concentration > 0.85:
            flags.append("concentrated_holdings")
        if fv.permission_bypass_attempts > 5:
            flags.append("permission_bypass_attempts")
        return flags

    def _fallback(self, address: str) -> dict:
        return {
            "address": address,
            "rug_probability": None,
            "ml_score": None,
            "composite_score": None,
            "verdict": "UNKNOWN",
            "breakdown": {"behavioral": None, "token_health": None, "threat": None, "community": None},
            "risk_flags": ["model_not_loaded"],
            "feature_vector": {},
            "top_drivers": [],
        }

    def get_feature_importances(self) -> dict[str, float]:
        return dict(self._fi)
