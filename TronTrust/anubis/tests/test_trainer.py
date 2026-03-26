"""
Tests for the Anubis trainer and predictor.
Run with: pytest tests/ -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest
import xgboost as xgb

from features.schema import AgentFeatureVector, AGENT_FEATURES, FEATURE_BOUNDS
from models.trainer import generate_synthetic_dataset, train
from engine.predictor import AnubisPredictor
from engine.monte_carlo import MonteCarloSimulator


# ---------------------------------------------------------------------------
# Feature schema
# ---------------------------------------------------------------------------

def test_feature_count():
    assert len(AGENT_FEATURES) == 50


def test_feature_bounds_coverage():
    for name in AGENT_FEATURES:
        assert name in FEATURE_BOUNDS, f"Missing bounds for {name}"


def test_feature_vector_to_numpy():
    fv = AgentFeatureVector(address="TXyz123" + "a" * 27)
    arr = fv.to_numpy()
    assert arr.shape == (50,)
    assert arr.dtype == np.float32


def test_feature_vector_clamp():
    fv = AgentFeatureVector(address="T" + "a" * 33)
    fv.justlend_repayment_rate = 999.0  # out of bounds
    fv.wallet_age_days = -5.0
    fv.clamp()
    assert fv.justlend_repayment_rate <= 1.0
    assert fv.wallet_age_days >= 0.0


# ---------------------------------------------------------------------------
# Synthetic dataset
# ---------------------------------------------------------------------------

def test_dataset_shape():
    X, y = generate_synthetic_dataset(n_samples=500)
    assert X.shape == (500, 50)
    assert y.shape == (500,)


def test_dataset_label_distribution():
    X, y = generate_synthetic_dataset(n_samples=2000)
    risky_ratio = y.mean()
    # Should be around 35% risky
    assert 0.25 < risky_ratio < 0.45, f"Unexpected risky ratio: {risky_ratio:.2f}"


def test_dataset_no_nan():
    X, y = generate_synthetic_dataset(n_samples=1000)
    assert not np.isnan(X).any(), "NaN values in feature matrix"
    assert not np.isnan(y).any()


def test_dataset_within_bounds():
    X, y = generate_synthetic_dataset(n_samples=500)
    for i, name in enumerate(AGENT_FEATURES):
        lo, hi = FEATURE_BOUNDS[name]
        assert X[:, i].min() >= lo - 1e-3, f"{name} below lower bound"
        assert X[:, i].max() <= hi + 1e-3, f"{name} above upper bound"


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def trained_model(tmp_path_factory):
    model_path = tmp_path_factory.mktemp("models") / "test_model.json"
    model = train(n_samples=5000, eval_mode=False, model_path=model_path)
    return model, model_path


def test_model_trains(trained_model):
    model, _ = trained_model
    assert isinstance(model, xgb.XGBClassifier)


def test_model_predict_shape(trained_model):
    model, _ = trained_model
    X, _ = generate_synthetic_dataset(n_samples=100)
    probs = model.predict_proba(X)
    assert probs.shape == (100, 2)
    assert (probs >= 0).all() and (probs <= 1).all()


def test_model_auc(trained_model):
    from sklearn.metrics import roc_auc_score
    model, _ = trained_model
    X, y = generate_synthetic_dataset(n_samples=2000, seed=99)
    probs = model.predict_proba(X)[:, 1]
    auc = roc_auc_score(y, probs)
    # Should be comfortably above 0.85 on synthetic data
    assert auc > 0.85, f"AUC too low: {auc:.4f}"


def test_feature_importance_top_features(trained_model):
    """justlend_repayment_rate and wallet_age_days must be in top-10."""
    model, _ = trained_model
    fi = dict(zip(AGENT_FEATURES, model.feature_importances_))
    top10 = {name for name, _ in sorted(fi.items(), key=lambda x: -x[1])[:10]}
    assert "justlend_repayment_rate" in top10, "justlend_repayment_rate not in top-10"
    assert "wallet_age_days" in top10, "wallet_age_days not in top-10"


def test_trustworthy_scores_higher(trained_model):
    """Trustworthy wallets should score significantly higher than risky ones."""
    from models.trainer import _generate_trustworthy, _generate_risky
    import numpy as np
    model, _ = trained_model
    rng = np.random.default_rng(42)
    X_trust = _generate_trustworthy(200, rng)
    X_risky = _generate_risky(200, rng)
    trust_scores = (1 - model.predict_proba(X_trust)[:, 1]) * 100
    risky_scores = (1 - model.predict_proba(X_risky)[:, 1]) * 100
    assert trust_scores.mean() > risky_scores.mean() + 20, (
        f"Gap too small: trust={trust_scores.mean():.1f} risky={risky_scores.mean():.1f}"
    )


# ---------------------------------------------------------------------------
# Predictor
# ---------------------------------------------------------------------------

def test_predictor_with_model(trained_model):
    model, model_path = trained_model
    predictor = AnubisPredictor(model_path)
    assert predictor.is_ready

    fv = AgentFeatureVector(address="T" + "a" * 33)
    fv.wallet_age_days = 500.0
    fv.justlend_repayment_rate = 0.95
    result = predictor.predict(fv)

    assert "rug_probability" in result
    assert 0 <= result["rug_probability"] <= 1
    assert 0 <= result["ml_score"] <= 100
    assert result["verdict"] in {"TRUSTED", "REPUTABLE", "CAUTION", "RISKY", "BLACKLISTED"}


def test_predictor_flags_new_wallet(trained_model):
    _, model_path = trained_model
    predictor = AnubisPredictor(model_path)
    fv = AgentFeatureVector(address="T" + "b" * 33)
    fv.wallet_age_days = 5.0
    result = predictor.predict(fv)
    assert "new_wallet" in result["risk_flags"]


def test_predictor_flags_honeypot(trained_model):
    _, model_path = trained_model
    predictor = AnubisPredictor(model_path)
    fv = AgentFeatureVector(address="T" + "c" * 33)
    fv.honeypot_probability = 0.9
    result = predictor.predict(fv)
    assert "honeypot_risk" in result["risk_flags"]


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------

def test_monte_carlo(trained_model):
    model, _ = trained_model
    simulator = MonteCarloSimulator(model, n_simulations=500)
    fv = AgentFeatureVector(address="T" + "d" * 33)
    fv.wallet_age_days = 300.0
    fv.justlend_repayment_rate = 0.9
    result = simulator.simulate(fv)
    assert result.p5 <= result.p25 <= result.p50 <= result.p75 <= result.p95
    assert 0 <= result.p5 <= 100
    assert result.stability_rating in {"STABLE", "MODERATE", "VOLATILE"}


def test_monte_carlo_volatile_wallet(trained_model):
    """High-volatility tokens should have wider confidence bands."""
    model, _ = trained_model
    simulator = MonteCarloSimulator(model, n_simulations=500)

    fv_stable = AgentFeatureVector(address="T" + "e" * 33)
    fv_stable.wallet_age_days = 800.0
    fv_stable.justlend_repayment_rate = 0.99

    fv_volatile = AgentFeatureVector(address="T" + "f" * 33)
    fv_volatile.wallet_age_days = 15.0
    fv_volatile.price_volatility_7d = 80.0
    fv_volatile.honeypot_probability = 0.5

    r_stable = simulator.simulate(fv_stable)
    r_volatile = simulator.simulate(fv_volatile)

    iqr_stable = r_stable.p75 - r_stable.p25
    iqr_volatile = r_volatile.p75 - r_volatile.p25
    # Volatile should have wider IQR (or at least not narrower)
    # Loose check due to stochastic nature
    assert iqr_stable <= iqr_volatile + 5, (
        f"Stable IQR ({iqr_stable:.1f}) unexpectedly larger than volatile ({iqr_volatile:.1f})"
    )
