"""
Retrain Anubis on Real Tron Wallet Data
========================================
Loads data/real/features.csv (collected by collect_real_data.py),
blends it with synthetic data for regularization, and retrains
the XGBoost model.

Why blend with synthetic?
  Real labeled data will be small (20-100 wallets initially).
  Pure real-data training overfits badly on small sets.
  Blending at ~20% real / 80% synthetic gives a model that has
  calibrated real-world priors while the real data steers it.
  As you collect more real labels, raise REAL_DATA_WEIGHT toward 1.0.

Usage:
    python3 scripts/retrain_on_real_data.py
    python3 scripts/retrain_on_real_data.py --real-weight 0.5   # more weight on real
    python3 scripts/retrain_on_real_data.py --real-only          # skip synthetic entirely
    python3 scripts/retrain_on_real_data.py --eval               # run cross-validation
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_validate
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.schema import AGENT_FEATURES, FEATURE_BOUNDS
from models.trainer import (
    generate_synthetic_dataset,
    MODEL_PATH,
    META_PATH,
    RANDOM_SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("retrain")

REAL_DATA_PATH  = Path(__file__).parent.parent / "data" / "real" / "features.csv"
TOKEN_DATA_PATH = Path(__file__).parent.parent / "data" / "real" / "token_features.csv"
REAL_DATA_WEIGHT = 0.2   # fraction of total dataset from real data (rest = synthetic)
N_SYNTHETIC      = 10_000  # synthetic samples to blend with


def load_real_data(data_path: Optional[Path] = None) -> tuple[np.ndarray, np.ndarray]:
    path = data_path or REAL_DATA_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"No real data found at {path}. "
            "Run scripts/collect_real_data.py or scripts/collect_token_data.py first."
        )

    df = pd.read_csv(path)
    logger.info("Loaded %d real samples from %s", len(df), path)

    missing = [f for f in AGENT_FEATURES if f not in df.columns]
    if missing:
        logger.warning("Missing features in real data (will zero-fill): %s", missing)
        for col in missing:
            df[col] = 0.0

    X = df[AGENT_FEATURES].fillna(0.0).values.astype(np.float32)
    y = df["label"].values.astype(np.float32)

    # Clamp real data to feature bounds (protects against API returning weird values)
    for i, name in enumerate(AGENT_FEATURES):
        lo, hi = FEATURE_BOUNDS[name]
        X[:, i] = np.clip(X[:, i], lo, hi)

    label_counts = {0: int((y == 0).sum()), 1: int((y == 1).sum())}
    logger.info("Real label distribution: %s", label_counts)
    return X, y


def blend_datasets(
    X_real: np.ndarray,
    y_real: np.ndarray,
    real_weight: float,
    n_synthetic: int,
    seed: int = RANDOM_SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Upsample real data to `real_weight` fraction of total dataset.
    Fill the rest with synthetic.
    """
    n_real = len(y_real)
    n_total_target = int(n_real / real_weight)
    n_synth = n_total_target - n_real

    logger.info(
        "Blending: %d real (%.0f%%) + %d synthetic = %d total",
        n_real, real_weight * 100, n_synth, n_total_target,
    )

    X_synth, y_synth = generate_synthetic_dataset(n_samples=n_synth, seed=seed)

    X = np.vstack([X_real, X_synth]).astype(np.float32)
    y = np.hstack([y_real, y_synth]).astype(np.float32)

    # Shuffle
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    return X[idx], y[idx]


def retrain(
    real_weight: float = REAL_DATA_WEIGHT,
    real_only: bool = False,
    eval_mode: bool = False,
    data_path: Optional[Path] = None,
):
    X_real, y_real = load_real_data(data_path)

    if real_only:
        logger.info("Training on real data only (%d samples)", len(y_real))
        X, y = X_real, y_real
    else:
        X, y = blend_datasets(X_real, y_real, real_weight, N_SYNTHETIC)

    df = pd.DataFrame(X, columns=AGENT_FEATURES)
    logger.info("Final dataset: %d samples, %.1f%% risky", len(y), y.mean() * 100)

    if len(y) < 20:
        logger.warning(
            "Very small dataset (%d samples). Scores will be unreliable. "
            "Collect more labeled wallets before trusting production scores.",
            len(y),
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
        scale_pos_weight=max((1 - y.mean()) / y.mean(), 0.1),
        eval_metric="logloss",
        random_state=RANDOM_SEED,
        n_jobs=-1,
        tree_method="hist",
    )

    if eval_mode and len(y) >= 20:
        logger.info("Running 5-fold cross-validation...")
        cv = StratifiedKFold(n_splits=min(5, int(y.sum())), shuffle=True, random_state=RANDOM_SEED)
        cv_results = cross_validate(
            model, df, y,
            cv=cv,
            scoring=["roc_auc", "average_precision"],
            n_jobs=-1,
        )
        logger.info("CV ROC-AUC:  %.4f ± %.4f",
                    cv_results["test_roc_auc"].mean(), cv_results["test_roc_auc"].std())
        logger.info("CV Avg-Prec: %.4f ± %.4f",
                    cv_results["test_average_precision"].mean(), cv_results["test_average_precision"].std())

    logger.info("Training final model...")
    model.fit(df, y)

    fi = dict(zip(AGENT_FEATURES, model.feature_importances_))
    top5 = sorted(fi.items(), key=lambda x: -x[1])[:5]
    logger.info("Top-5 features:")
    for rank, (name, score) in enumerate(top5, 1):
        logger.info("  %d. %s = %.4f", rank, name, score)

    # Save (overwrites the synthetic-trained model)
    model.save_model(str(MODEL_PATH))
    logger.info("Model saved to %s", MODEL_PATH)

    meta = {
        "feature_names": AGENT_FEATURES,
        "feature_importances": {k: float(v) for k, v in fi.items()},
        "top_features": [n for n, _ in sorted(fi.items(), key=lambda x: -x[1])[:10]],
        "n_samples_trained": int(len(y)),
        "n_real_samples": int(len(y_real)),
        "risky_ratio": float(y.mean()),
        "model_version": "anubis_v1",
        "trained_on": "blend" if not real_only else "real_only",
        "real_weight": real_weight if not real_only else 1.0,
        "data_source": str(data_path) if data_path else str(REAL_DATA_PATH),
    }
    META_PATH.write_text(json.dumps(meta, indent=2))
    logger.info("Metadata saved to %s", META_PATH)

    logger.info(
        "\nDone. Restart the Anubis server to load the new model:\n"
        "  uvicorn main:app --reload"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-weight", type=float, default=REAL_DATA_WEIGHT,
                        help="Fraction of total training data from real data (default 0.2)")
    parser.add_argument("--real-only", action="store_true",
                        help="Train on real data only (no synthetic blending)")
    parser.add_argument("--eval", action="store_true",
                        help="Run cross-validation before final training")
    parser.add_argument(
        "--data-path", type=str, default=None,
        help=(
            "Path to labeled CSV (address + 50 features + label). "
            f"Defaults to {REAL_DATA_PATH}. "
            f"Use {TOKEN_DATA_PATH} for token-based training."
        ),
    )
    args = parser.parse_args()

    retrain(
        real_weight=args.real_weight,
        real_only=args.real_only,
        eval_mode=args.eval,
        data_path=Path(args.data_path) if args.data_path else None,
    )
