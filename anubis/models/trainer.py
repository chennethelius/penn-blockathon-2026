"""
Anubis XGBoost Trainer
======================
Trains a binary classifier (0 = safe token, 1 = rug / scam token) on synthetic
Tron-native data calibrated for TOKEN-CENTRIC risk assessment.

The model answers: "Will this token rug pull?"
Key discriminators are token health features (indices 25-39):
  honeypot_probability, top10_holder_concentration, token_age_days,
  token_liquidity_usd, audit_score, freeze/mint/blacklist functions.

Wallet behavioral features (indices 0-24) are realistic but intentionally
overlapping between classes so the model does NOT learn to distinguish
tokens by the deployer wallet's age or repayment history.

Usage:
    python -m models.trainer            # train and save to models/anubis_v1.json
    python -m models.trainer --eval     # also print cross-validation metrics
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import roc_auc_score, average_precision_score, classification_report
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).parent.parent))
from features.schema import AGENT_FEATURES, FEATURE_BOUNDS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

RANDOM_SEED = 42
N_SAMPLES = 50_000          # synthetic dataset size
MODEL_PATH  = Path(__file__).parent / "anubis_v1.json"
META_PATH   = Path(__file__).parent / "anubis_v1_meta.json"
SCALER_PATH = Path(__file__).parent / "scaler.json"


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def _rng(seed: int = RANDOM_SEED) -> np.random.Generator:
    return np.random.default_rng(seed)


def _generate_trustworthy(n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Generate safe token feature vectors.
    Characteristics: established tokens with deep liquidity, distributed
    holders, renounced ownership, audited contracts, no honeypot signals.

    Wallet behavioral features are realistic but intentionally overlapping
    with the risky class — they are NOT the primary discriminators here.
    """
    X = np.zeros((n, 50), dtype=np.float32)
    idx = {name: i for i, name in enumerate(AGENT_FEATURES)}

    # BEHAVIORAL — realistic but NOT the primary signal; wide overlap with risky
    X[:, idx["wallet_age_days"]]             = rng.uniform(30, 1500, n)   # wide overlap
    X[:, idx["tx_count_total"]]              = rng.integers(50, 30000, n).astype(float)
    X[:, idx["tx_count_30d"]]               = rng.integers(5, 1500, n).astype(float)
    X[:, idx["tx_count_7d"]]                = rng.integers(1, 400, n).astype(float)
    X[:, idx["unique_counterparties_total"]] = rng.integers(20, 4000, n).astype(float)
    X[:, idx["unique_counterparties_30d"]]   = rng.integers(5, 400, n).astype(float)
    X[:, idx["avg_tx_value_usdt"]]           = rng.lognormal(3.5, 1.5, n).astype(float)
    X[:, idx["max_tx_value_usdt"]]           = X[:, idx["avg_tx_value_usdt"]] * rng.uniform(2, 20, n)
    X[:, idx["usdt_tx_ratio"]]               = rng.beta(4, 4, n).astype(float)
    X[:, idx["contract_interaction_ratio"]]  = rng.beta(4, 4, n).astype(float)
    X[:, idx["smart_contract_deployments"]]  = rng.integers(0, 15, n).astype(float)
    X[:, idx["days_since_last_tx"]]          = rng.uniform(0, 60, n)
    X[:, idx["trx_balance_current"]]         = rng.lognormal(5, 2, n)
    X[:, idx["usdt_balance_current"]]        = rng.lognormal(4, 2, n)
    X[:, idx["energy_usage_pattern"]]        = rng.choice([0, 1], n, p=[0.3, 0.7]).astype(float)
    X[:, idx["bandwidth_efficiency_ratio"]]  = rng.beta(5, 3, n).astype(float)
    X[:, idx["trc20_token_diversity"]]       = rng.integers(1, 40, n).astype(float)
    X[:, idx["justlend_repayment_rate"]]     = rng.beta(5, 3, n).astype(float)   # moderate, wide overlap
    X[:, idx["justlend_total_borrowed_usdt"]]= rng.lognormal(6, 2, n)
    X[:, idx["justlend_total_repaid_usdt"]]  = (
        X[:, idx["justlend_total_borrowed_usdt"]] * rng.beta(5, 3, n)
    )
    X[:, idx["sunswap_trade_frequency"]]     = rng.integers(2, 400, n).astype(float)
    X[:, idx["sunswap_wash_trading_score"]]  = rng.beta(1, 7, n).astype(float)
    X[:, idx["lp_manipulation_score"]]       = rng.beta(1, 7, n).astype(float)
    X[:, idx["commercial_payment_on_time_rate"]] = rng.beta(6, 3, n).astype(float)
    X[:, idx["invoice_completion_rate"]]     = rng.beta(6, 3, n).astype(float)

    # TOKEN HEALTH — these ARE the primary discriminators for safe tokens
    X[:, idx["token_liquidity_usd"]]         = rng.lognormal(10, 1.5, n)       # deep liquidity
    X[:, idx["token_holder_count"]]          = rng.integers(500, 200000, n).astype(float)  # many holders
    X[:, idx["top10_holder_concentration"]]  = rng.beta(2, 7, n).astype(float)  # distributed
    X[:, idx["token_age_days"]]              = rng.uniform(90, 1500, n)          # established
    X[:, idx["price_volatility_7d"]]         = rng.beta(2, 8, n).astype(float) * 25
    X[:, idx["volume_to_liquidity_ratio"]]   = rng.beta(3, 6, n).astype(float) * 1.5  # healthy
    X[:, idx["honeypot_probability"]]        = rng.beta(1, 30, n).astype(float)  # very low
    X[:, idx["freeze_function_present"]]     = rng.choice([0, 1], n, p=[0.90, 0.10]).astype(float)
    X[:, idx["mint_function_present"]]       = rng.choice([0, 1], n, p=[0.80, 0.20]).astype(float)
    X[:, idx["owner_renounced"]]             = rng.choice([0, 1], n, p=[0.15, 0.85]).astype(float)  # mostly renounced
    X[:, idx["audit_score"]]                 = rng.choice([0, 1, 2], n, p=[0.10, 0.35, 0.55]).astype(float)  # mostly audited
    X[:, idx["dex_listings_count"]]          = rng.integers(3, 15, n).astype(float)
    X[:, idx["transfer_tax_rate"]]           = rng.beta(1, 25, n).astype(float)  # near zero
    X[:, idx["max_transaction_limit_present"]] = rng.choice([0, 1], n, p=[0.85, 0.15]).astype(float)
    X[:, idx["blacklist_function_present"]]  = rng.choice([0, 1], n, p=[0.85, 0.15]).astype(float)

    # NETWORK / THREAT — mostly clean
    X[:, idx["payment_graph_centrality"]]    = rng.beta(4, 4, n).astype(float)
    X[:, idx["counterparty_avg_trust_score"]]= rng.normal(65, 12, n).clip(30, 100)
    X[:, idx["incoming_tx_diversity_score"]] = rng.beta(5, 3, n).astype(float)
    X[:, idx["outgoing_tx_diversity_score"]] = rng.beta(5, 3, n).astype(float)
    X[:, idx["circular_payment_ratio"]]      = rng.beta(1, 10, n).astype(float)
    X[:, idx["energy_drain_victim_count"]]   = rng.integers(0, 3, n).astype(float)
    X[:, idx["phishing_contract_association_score"]] = rng.beta(1, 20, n).astype(float)
    X[:, idx["mixer_interaction_score"]]     = rng.beta(1, 15, n).astype(float)
    X[:, idx["address_poisoning_attempts"]]  = rng.integers(0, 3, n).astype(float)
    X[:, idx["permission_bypass_attempts"]]  = rng.integers(0, 3, n).astype(float)

    return X


def _generate_risky(n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Generate realistic risky/rug wallet feature vectors.
    Multiple sub-profiles: new rug wallets, wash traders, honeypot deployers,
    energy drain attackers, phishing operators.

    IMPORTANT: We first fill ALL features with realistic background noise
    (similar distribution to trustworthy wallets) so that only the
    profile-specific "bad" signals discriminate classes. This prevents
    trivially-separable zero-valued features from dominating importance.
    """
    idx = {name: i for i, name in enumerate(AGENT_FEATURES)}

    # ------------------------------------------------------------------
    # Step 1: realistic background (same distributions as trustworthy)
    # ------------------------------------------------------------------
    X = np.zeros((n, 50), dtype=np.float32)

    X[:, idx["tx_count_total"]]              = rng.integers(100, 20000, n).astype(float)
    X[:, idx["tx_count_30d"]]               = rng.integers(5, 1000, n).astype(float)
    X[:, idx["tx_count_7d"]]                = rng.integers(1, 300, n).astype(float)
    X[:, idx["unique_counterparties_total"]] = rng.integers(10, 2000, n).astype(float)
    X[:, idx["unique_counterparties_30d"]]   = rng.integers(3, 300, n).astype(float)
    X[:, idx["avg_tx_value_usdt"]]           = rng.lognormal(3, 1.5, n).astype(float)
    X[:, idx["max_tx_value_usdt"]]           = X[:, idx["avg_tx_value_usdt"]] * rng.uniform(1.5, 15, n)
    X[:, idx["usdt_tx_ratio"]]               = rng.beta(3, 4, n).astype(float)
    X[:, idx["contract_interaction_ratio"]]  = rng.beta(3, 5, n).astype(float)
    X[:, idx["smart_contract_deployments"]]  = rng.integers(0, 8, n).astype(float)
    X[:, idx["wallet_age_days"]]             = rng.uniform(30, 600, n)  # overlap region
    X[:, idx["days_since_last_tx"]]          = rng.uniform(0, 60, n)
    X[:, idx["trx_balance_current"]]         = rng.lognormal(5, 2, n)
    X[:, idx["usdt_balance_current"]]        = rng.lognormal(4, 2, n)
    X[:, idx["energy_usage_pattern"]]        = rng.choice([0, 1], n, p=[0.5, 0.5]).astype(float)
    X[:, idx["bandwidth_efficiency_ratio"]]  = rng.beta(4, 4, n).astype(float)
    X[:, idx["trc20_token_diversity"]]       = rng.integers(1, 30, n).astype(float)  # NOT zero
    X[:, idx["justlend_repayment_rate"]]     = rng.beta(3, 5, n).astype(float)  # lower but overlapping
    X[:, idx["justlend_total_borrowed_usdt"]]= rng.lognormal(6, 2, n)
    X[:, idx["justlend_total_repaid_usdt"]]  = (
        X[:, idx["justlend_total_borrowed_usdt"]] * rng.beta(3, 5, n)
    )
    X[:, idx["sunswap_trade_frequency"]]     = rng.integers(2, 300, n).astype(float)
    X[:, idx["sunswap_wash_trading_score"]]  = rng.beta(2, 5, n).astype(float)
    X[:, idx["lp_manipulation_score"]]       = rng.beta(2, 6, n).astype(float)
    X[:, idx["commercial_payment_on_time_rate"]] = rng.beta(3, 5, n).astype(float)
    X[:, idx["invoice_completion_rate"]]     = rng.beta(3, 5, n).astype(float)

    X[:, idx["token_liquidity_usd"]]         = rng.lognormal(7, 2, n)
    X[:, idx["token_holder_count"]]          = rng.integers(10, 5000, n).astype(float)  # NOT tiny
    X[:, idx["top10_holder_concentration"]]  = rng.beta(5, 3, n).astype(float)
    X[:, idx["token_age_days"]]              = rng.uniform(15, 500, n)
    X[:, idx["price_volatility_7d"]]         = rng.beta(4, 4, n).astype(float) * 50
    X[:, idx["volume_to_liquidity_ratio"]]   = rng.beta(4, 4, n).astype(float) * 5
    X[:, idx["honeypot_probability"]]        = rng.beta(2, 6, n).astype(float)
    X[:, idx["freeze_function_present"]]     = rng.choice([0, 1], n, p=[0.5, 0.5]).astype(float)
    X[:, idx["mint_function_present"]]       = rng.choice([0, 1], n, p=[0.4, 0.6]).astype(float)
    X[:, idx["owner_renounced"]]             = rng.choice([0, 1], n, p=[0.6, 0.4]).astype(float)
    X[:, idx["audit_score"]]                 = rng.choice([0, 1, 2], n, p=[0.6, 0.3, 0.1]).astype(float)
    X[:, idx["dex_listings_count"]]          = rng.integers(1, 6, n).astype(float)
    X[:, idx["transfer_tax_rate"]]           = rng.beta(2, 8, n).astype(float)
    X[:, idx["max_transaction_limit_present"]] = rng.choice([0, 1], n, p=[0.5, 0.5]).astype(float)
    X[:, idx["blacklist_function_present"]]  = rng.choice([0, 1], n, p=[0.4, 0.6]).astype(float)

    X[:, idx["payment_graph_centrality"]]    = rng.beta(3, 5, n).astype(float)
    X[:, idx["counterparty_avg_trust_score"]]= rng.normal(45, 15, n).clip(10, 80)
    X[:, idx["incoming_tx_diversity_score"]] = rng.beta(3, 5, n).astype(float)
    X[:, idx["outgoing_tx_diversity_score"]] = rng.beta(3, 5, n).astype(float)
    X[:, idx["circular_payment_ratio"]]      = rng.beta(2, 6, n).astype(float)
    X[:, idx["energy_drain_victim_count"]]   = rng.integers(0, 3, n).astype(float)
    X[:, idx["phishing_contract_association_score"]] = rng.beta(1, 8, n).astype(float)
    X[:, idx["mixer_interaction_score"]]     = rng.beta(1, 7, n).astype(float)
    X[:, idx["address_poisoning_attempts"]]  = rng.integers(0, 3, n).astype(float)
    X[:, idx["permission_bypass_attempts"]]  = rng.integers(0, 3, n).astype(float)

    # ------------------------------------------------------------------
    # Step 2: apply profile-specific SIGNAL overrides (on top of background)
    # ------------------------------------------------------------------
    profiles = rng.choice(
        ["rug_new", "wash_trader", "honeypot", "energy_drain", "phishing"],
        n,
        p=[0.25, 0.20, 0.25, 0.15, 0.15],
    )

    for profile in np.unique(profiles):
        mask = profiles == profile
        m = mask.sum()

        if profile == "rug_new":
            # Very new wallet; poor repayment; honeypot token; tiny holder base
            X[mask, idx["wallet_age_days"]]             = rng.uniform(0, 25, m)
            X[mask, idx["justlend_repayment_rate"]]     = rng.beta(1, 8, m).astype(float)
            X[mask, idx["honeypot_probability"]]        = rng.beta(7, 2, m).astype(float)
            X[mask, idx["owner_renounced"]]             = np.zeros(m)
            X[mask, idx["mint_function_present"]]       = np.ones(m)
            X[mask, idx["freeze_function_present"]]     = np.ones(m)
            X[mask, idx["audit_score"]]                 = np.zeros(m)
            X[mask, idx["top10_holder_concentration"]]  = rng.beta(9, 1, m).astype(float)
            X[mask, idx["token_holder_count"]]          = rng.integers(1, 25, m).astype(float)
            X[mask, idx["token_liquidity_usd"]]         = rng.uniform(0, 3000, m)
            X[mask, idx["price_volatility_7d"]]         = rng.uniform(50, 90, m)
            X[mask, idx["counterparty_avg_trust_score"]]= rng.normal(20, 10, m).clip(0, 45)

        elif profile == "wash_trader":
            # High wash trading score; circular payments; low unique counterparties
            X[mask, idx["wallet_age_days"]]             = rng.uniform(20, 180, m)
            X[mask, idx["sunswap_wash_trading_score"]]  = rng.beta(8, 2, m).astype(float)
            X[mask, idx["lp_manipulation_score"]]       = rng.beta(7, 2, m).astype(float)
            X[mask, idx["circular_payment_ratio"]]      = rng.beta(7, 2, m).astype(float)
            X[mask, idx["unique_counterparties_total"]] = rng.integers(1, 8, m).astype(float)
            X[mask, idx["justlend_repayment_rate"]]     = rng.beta(2, 7, m).astype(float)
            X[mask, idx["mixer_interaction_score"]]     = rng.beta(5, 3, m).astype(float)
            X[mask, idx["counterparty_avg_trust_score"]]= rng.normal(30, 12, m).clip(0, 55)

        elif profile == "honeypot":
            # High honeypot probability; active freeze+blacklist; no audit; tiny holders
            X[mask, idx["honeypot_probability"]]        = rng.beta(9, 1, m).astype(float)
            X[mask, idx["freeze_function_present"]]     = np.ones(m)
            X[mask, idx["blacklist_function_present"]]  = np.ones(m)
            X[mask, idx["transfer_tax_rate"]]           = rng.uniform(0.15, 0.5, m)
            X[mask, idx["max_transaction_limit_present"]]= np.ones(m)
            X[mask, idx["audit_score"]]                 = np.zeros(m)
            X[mask, idx["owner_renounced"]]             = np.zeros(m)
            X[mask, idx["top10_holder_concentration"]]  = rng.beta(8, 1, m).astype(float)
            X[mask, idx["token_holder_count"]]          = rng.integers(2, 18, m).astype(float)
            X[mask, idx["wallet_age_days"]]             = rng.uniform(5, 80, m)
            X[mask, idx["justlend_repayment_rate"]]     = rng.beta(1, 9, m).astype(float)
            X[mask, idx["counterparty_avg_trust_score"]]= rng.normal(15, 10, m).clip(0, 40)

        elif profile == "energy_drain":
            # Energy drain victim count; permission bypass; irregular energy usage
            X[mask, idx["energy_drain_victim_count"]]   = rng.integers(8, 200, m).astype(float)
            X[mask, idx["permission_bypass_attempts"]]  = rng.integers(5, 100, m).astype(float)
            X[mask, idx["energy_usage_pattern"]]        = np.zeros(m)
            X[mask, idx["wallet_age_days"]]             = rng.uniform(10, 100, m)
            X[mask, idx["contract_interaction_ratio"]]  = rng.beta(8, 2, m).astype(float)
            X[mask, idx["smart_contract_deployments"]]  = rng.integers(3, 30, m).astype(float)
            X[mask, idx["phishing_contract_association_score"]] = rng.beta(6, 2, m).astype(float)
            X[mask, idx["justlend_repayment_rate"]]     = rng.beta(1, 6, m).astype(float)
            X[mask, idx["counterparty_avg_trust_score"]]= rng.normal(25, 12, m).clip(0, 50)

        elif profile == "phishing":
            # Phishing score; address poisoning; mixer usage; new wallet
            X[mask, idx["phishing_contract_association_score"]] = rng.beta(9, 1, m).astype(float)
            X[mask, idx["address_poisoning_attempts"]]  = rng.integers(12, 300, m).astype(float)
            X[mask, idx["mixer_interaction_score"]]     = rng.beta(7, 2, m).astype(float)
            X[mask, idx["wallet_age_days"]]             = rng.uniform(1, 55, m)
            X[mask, idx["justlend_repayment_rate"]]     = rng.beta(1, 9, m).astype(float)
            X[mask, idx["counterparty_avg_trust_score"]]= rng.normal(10, 8, m).clip(0, 30)

    return X


def generate_synthetic_dataset(
    n_samples: int = N_SAMPLES,
    risky_ratio: float = 0.35,
    seed: int = RANDOM_SEED,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns (X, y) where y=1 means risky.
    Slight class imbalance (35% risky) mirrors real-world distribution.
    """
    rng = _rng(seed)
    n_risky = int(n_samples * risky_ratio)
    n_trust = n_samples - n_risky

    X_trust = _generate_trustworthy(n_trust, rng)
    X_risky = _generate_risky(n_risky, rng)

    X = np.vstack([X_trust, X_risky]).astype(np.float32)
    y = np.hstack([np.zeros(n_trust), np.ones(n_risky)]).astype(np.float32)

    # Shuffle
    idx = rng.permutation(len(y))
    return X[idx], y[idx]


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    n_samples: int = N_SAMPLES,
    eval_mode: bool = False,
    model_path: Path = MODEL_PATH,
) -> xgb.XGBClassifier:
    logger.info("Generating synthetic dataset (%d samples)...", n_samples)
    X, y = generate_synthetic_dataset(n_samples)

    df = pd.DataFrame(X, columns=AGENT_FEATURES)
    logger.info(
        "Dataset: %d samples, %.1f%% risky",
        len(y), y.mean() * 100,
    )

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=1.0,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=(1 - y.mean()) / y.mean(),  # handle class imbalance
        eval_metric="logloss",
        random_state=RANDOM_SEED,
        n_jobs=-1,
        tree_method="hist",
        enable_categorical=False,
    )

    if eval_mode:
        logger.info("Running 5-fold cross-validation...")
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
        cv_results = cross_validate(
            model, df, y,
            cv=cv,
            scoring=["roc_auc", "average_precision"],
            return_train_score=True,
            n_jobs=-1,
        )
        logger.info("CV ROC-AUC:  %.4f ± %.4f", cv_results["test_roc_auc"].mean(), cv_results["test_roc_auc"].std())
        logger.info("CV Avg-Prec: %.4f ± %.4f", cv_results["test_average_precision"].mean(), cv_results["test_average_precision"].std())

    logger.info("Training final model on full dataset...")
    model.fit(df, y)

    # --- Feature importance check ---
    fi = dict(zip(AGENT_FEATURES, model.feature_importances_))
    top5 = sorted(fi.items(), key=lambda x: -x[1])[:5]
    logger.info("Top-5 features by importance:")
    for rank, (name, score) in enumerate(top5, 1):
        logger.info("  %d. %s = %.4f", rank, name, score)

    # Verify key features rank in top-10
    top10_names = {name for name, _ in sorted(fi.items(), key=lambda x: -x[1])[:10]}
    for critical in ["justlend_repayment_rate", "wallet_age_days"]:
        if critical not in top10_names:
            logger.warning(
                "Expected '%s' in top-10 features but it ranked %d",
                critical,
                sorted(fi.keys(), key=lambda k: -fi[k]).index(critical) + 1,
            )

    # --- Save ---
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))
    logger.info("Model saved to %s", model_path)

    # Save feature importance metadata alongside the model
    meta = {
        "feature_names": AGENT_FEATURES,
        "feature_importances": {k: float(v) for k, v in fi.items()},
        "top_features": [name for name, _ in sorted(fi.items(), key=lambda x: -x[1])[:10]],
        "n_samples_trained": int(len(y)),
        "risky_ratio": float(y.mean()),
        "model_version": "anubis_v1",
    }
    meta_path = META_PATH
    meta_path.write_text(json.dumps(meta, indent=2))
    logger.info("Metadata saved to %s", meta_path)

    return model


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Anubis XGBoost model")
    parser.add_argument("--eval", action="store_true", help="Run cross-validation")
    parser.add_argument("--samples", type=int, default=N_SAMPLES)
    args = parser.parse_args()
    train(n_samples=args.samples, eval_mode=args.eval)
