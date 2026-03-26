"""
Anubis Monte Carlo Simulation
==============================
Runs N simulations by perturbing the feature vector with calibrated noise,
then returns confidence intervals (p5, p25, p75, p95) on the trust score.

This gives API consumers a sense of how stable a wallet's score is —
a wallet with tight confidence intervals is consistently evaluated;
wide intervals indicate data uncertainty or borderline behavior.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import xgboost as xgb

from features.schema import (
    AgentFeatureVector,
    AGENT_FEATURES,
    FEATURE_BOUNDS,
    FEATURE_MC_NOISE,
    DEFAULT_MC_NOISE,
)

logger = logging.getLogger(__name__)

N_SIMULATIONS = 10_000
CONFIDENCE_LEVELS = [5, 25, 50, 75, 95]


@dataclass
class MonteCarloResult:
    n_simulations: int
    mean_score: float
    std_score: float
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    stability_rating: str  # STABLE | MODERATE | VOLATILE
    interpretation: str

    def to_dict(self) -> dict:
        return {
            "n_simulations": self.n_simulations,
            "mean_score": round(self.mean_score, 2),
            "std_score": round(self.std_score, 2),
            "percentiles": {
                "p5":  round(self.p5, 2),
                "p25": round(self.p25, 2),
                "p50": round(self.p50, 2),
                "p75": round(self.p75, 2),
                "p95": round(self.p95, 2),
            },
            "stability_rating": self.stability_rating,
            "interpretation": self.interpretation,
        }


class MonteCarloSimulator:
    """
    Perturbs input feature vectors and re-scores N times to compute
    confidence bands for the trust score.
    """

    def __init__(self, model: xgb.XGBClassifier, n_simulations: int = N_SIMULATIONS):
        self._model = model
        self._n = n_simulations

        # Precompute noise sigmas per feature (in feature units)
        self._sigmas = np.array(
            [
                FEATURE_MC_NOISE.get(name, DEFAULT_MC_NOISE)
                * (FEATURE_BOUNDS[name][1] - FEATURE_BOUNDS[name][0])
                for name in AGENT_FEATURES
            ],
            dtype=np.float32,
        )

        # Precompute bounds arrays for clipping
        self._lo = np.array([FEATURE_BOUNDS[n][0] for n in AGENT_FEATURES], dtype=np.float32)
        self._hi = np.array([FEATURE_BOUNDS[n][1] for n in AGENT_FEATURES], dtype=np.float32)

    def simulate(
        self,
        fv: AgentFeatureVector,
        rng: Optional[np.random.Generator] = None,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation for a single feature vector.
        Returns confidence bands for the trust score.
        """
        if rng is None:
            rng = np.random.default_rng()

        x_base = fv.to_numpy()  # shape (50,)

        # Generate N perturbed samples: (N, 50)
        noise = rng.normal(0.0, self._sigmas, size=(self._n, 50)).astype(np.float32)
        X_perturbed = np.clip(x_base + noise, self._lo, self._hi)

        # Batch predict — XGBoost handles large batches efficiently
        rug_probs = self._model.predict_proba(X_perturbed)[:, 1]
        scores = (1.0 - rug_probs) * 100.0

        pcts = np.percentile(scores, CONFIDENCE_LEVELS)
        std = float(np.std(scores))

        # Stability classification
        iqr = pcts[3] - pcts[1]  # p75 - p25
        if iqr < 5:
            stability = "STABLE"
            interpretation = (
                "Score is highly consistent across data uncertainty scenarios."
            )
        elif iqr < 15:
            stability = "MODERATE"
            interpretation = (
                "Some sensitivity to data uncertainty; score may shift ±{:.0f} points.".format(iqr / 2)
            )
        else:
            stability = "VOLATILE"
            interpretation = (
                "Score is highly sensitive to data quality; treat with caution. "
                "IQR={:.1f}".format(iqr)
            )

        return MonteCarloResult(
            n_simulations=self._n,
            mean_score=float(np.mean(scores)),
            std_score=std,
            p5=float(pcts[0]),
            p25=float(pcts[1]),
            p50=float(pcts[2]),
            p75=float(pcts[3]),
            p95=float(pcts[4]),
            stability_rating=stability,
            interpretation=interpretation,
        )
