"""
Anubis Feature Schema
50 Tron-native features for trust scoring.
Split: 25 behavioral, 15 token health, 10 network/threat.
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


# ---------------------------------------------------------------------------
# Canonical feature order — must never change after training
# ---------------------------------------------------------------------------
AGENT_FEATURES = [
    # BEHAVIORAL (0-24)
    "tx_count_total",
    "tx_count_30d",
    "tx_count_7d",
    "unique_counterparties_total",
    "unique_counterparties_30d",
    "avg_tx_value_usdt",
    "max_tx_value_usdt",
    "usdt_tx_ratio",
    "contract_interaction_ratio",
    "smart_contract_deployments",
    "wallet_age_days",
    "days_since_last_tx",
    "trx_balance_current",
    "usdt_balance_current",
    "energy_usage_pattern",
    "bandwidth_efficiency_ratio",
    "trc20_token_diversity",
    "justlend_repayment_rate",
    "justlend_total_borrowed_usdt",
    "justlend_total_repaid_usdt",
    "sunswap_trade_frequency",
    "sunswap_wash_trading_score",
    "lp_manipulation_score",
    "commercial_payment_on_time_rate",
    "invoice_completion_rate",
    # TOKEN HEALTH (25-39)
    "token_liquidity_usd",
    "token_holder_count",
    "top10_holder_concentration",
    "token_age_days",
    "price_volatility_7d",
    "volume_to_liquidity_ratio",
    "honeypot_probability",
    "freeze_function_present",
    "mint_function_present",
    "owner_renounced",
    "audit_score",
    "dex_listings_count",
    "transfer_tax_rate",
    "max_transaction_limit_present",
    "blacklist_function_present",
    # NETWORK / THREAT (40-49)
    "payment_graph_centrality",
    "counterparty_avg_trust_score",
    "incoming_tx_diversity_score",
    "outgoing_tx_diversity_score",
    "circular_payment_ratio",
    "energy_drain_victim_count",
    "phishing_contract_association_score",
    "mixer_interaction_score",
    "address_poisoning_attempts",
    "permission_bypass_attempts",
]

assert len(AGENT_FEATURES) == 50, "Feature set must have exactly 50 features"

FEATURE_IDX = {name: i for i, name in enumerate(AGENT_FEATURES)}

# Feature bounds for validation and Monte Carlo perturbation
FEATURE_BOUNDS = {
    "tx_count_total":                  (0, 500_000),
    "tx_count_30d":                    (0, 10_000),
    "tx_count_7d":                     (0, 3_000),
    "unique_counterparties_total":     (0, 50_000),
    "unique_counterparties_30d":       (0, 5_000),
    "avg_tx_value_usdt":               (0, 1_000_000),
    "max_tx_value_usdt":               (0, 10_000_000),
    "usdt_tx_ratio":                   (0.0, 1.0),
    "contract_interaction_ratio":      (0.0, 1.0),
    "smart_contract_deployments":      (0, 500),
    "wallet_age_days":                 (0, 3000),
    "days_since_last_tx":              (0, 3000),
    "trx_balance_current":             (0, 1_000_000_000),
    "usdt_balance_current":            (0, 100_000_000),
    "energy_usage_pattern":            (0, 1),
    "bandwidth_efficiency_ratio":      (0.0, 1.0),
    "trc20_token_diversity":           (0, 200),
    "justlend_repayment_rate":         (0.0, 1.0),
    "justlend_total_borrowed_usdt":    (0, 100_000_000),
    "justlend_total_repaid_usdt":      (0, 100_000_000),
    "sunswap_trade_frequency":         (0, 10_000),
    "sunswap_wash_trading_score":      (0.0, 1.0),
    "lp_manipulation_score":           (0.0, 1.0),
    "commercial_payment_on_time_rate": (0.0, 1.0),
    "invoice_completion_rate":         (0.0, 1.0),
    "token_liquidity_usd":             (0, 500_000_000),
    "token_holder_count":              (0, 2_000_000),
    "top10_holder_concentration":      (0.0, 1.0),
    "token_age_days":                  (0, 3000),
    "price_volatility_7d":             (0.0, 100.0),
    "volume_to_liquidity_ratio":       (0.0, 50.0),
    "honeypot_probability":            (0.0, 1.0),
    "freeze_function_present":         (0, 1),
    "mint_function_present":           (0, 1),
    "owner_renounced":                 (0, 1),
    "audit_score":                     (0, 2),
    "dex_listings_count":              (0, 20),
    "transfer_tax_rate":               (0.0, 1.0),
    "max_transaction_limit_present":   (0, 1),
    "blacklist_function_present":      (0, 1),
    "payment_graph_centrality":        (0.0, 1.0),
    "counterparty_avg_trust_score":    (0.0, 100.0),
    "incoming_tx_diversity_score":     (0.0, 1.0),
    "outgoing_tx_diversity_score":     (0.0, 1.0),
    "circular_payment_ratio":          (0.0, 1.0),
    "energy_drain_victim_count":       (0, 1000),
    "phishing_contract_association_score": (0.0, 1.0),
    "mixer_interaction_score":         (0.0, 1.0),
    "address_poisoning_attempts":      (0, 500),
    "permission_bypass_attempts":      (0, 500),
}

# Standard deviation multipliers for Monte Carlo perturbation (fraction of range)
FEATURE_MC_NOISE = {
    # Stable features — low perturbation
    "wallet_age_days":                 0.02,
    "justlend_repayment_rate":         0.03,
    "owner_renounced":                 0.0,   # binary — no perturbation
    "freeze_function_present":         0.0,
    "mint_function_present":           0.0,
    "blacklist_function_present":      0.0,
    "max_transaction_limit_present":   0.0,
    # Volatile features — higher perturbation
    "price_volatility_7d":             0.15,
    "volume_to_liquidity_ratio":       0.12,
    "sunswap_wash_trading_score":      0.10,
    "token_liquidity_usd":             0.10,
}

DEFAULT_MC_NOISE = 0.05  # 5% of feature range for unspecified features


@dataclass
class AgentFeatureVector:
    """Full 50-feature vector for an agent wallet."""
    address: str

    # BEHAVIORAL
    tx_count_total: float = 0.0
    tx_count_30d: float = 0.0
    tx_count_7d: float = 0.0
    unique_counterparties_total: float = 0.0
    unique_counterparties_30d: float = 0.0
    avg_tx_value_usdt: float = 0.0
    max_tx_value_usdt: float = 0.0
    usdt_tx_ratio: float = 0.0
    contract_interaction_ratio: float = 0.0
    smart_contract_deployments: float = 0.0
    wallet_age_days: float = 0.0
    days_since_last_tx: float = 999.0
    trx_balance_current: float = 0.0
    usdt_balance_current: float = 0.0
    energy_usage_pattern: float = 0.0
    bandwidth_efficiency_ratio: float = 0.5
    trc20_token_diversity: float = 0.0
    justlend_repayment_rate: float = 0.0
    justlend_total_borrowed_usdt: float = 0.0
    justlend_total_repaid_usdt: float = 0.0
    sunswap_trade_frequency: float = 0.0
    sunswap_wash_trading_score: float = 0.0
    lp_manipulation_score: float = 0.0
    commercial_payment_on_time_rate: float = 0.0
    invoice_completion_rate: float = 0.0

    # TOKEN HEALTH
    token_liquidity_usd: float = 0.0
    token_holder_count: float = 0.0
    top10_holder_concentration: float = 1.0
    token_age_days: float = 0.0
    price_volatility_7d: float = 0.0
    volume_to_liquidity_ratio: float = 0.0
    honeypot_probability: float = 0.0
    freeze_function_present: float = 0.0
    mint_function_present: float = 0.0
    owner_renounced: float = 0.0
    audit_score: float = 0.0
    dex_listings_count: float = 0.0
    transfer_tax_rate: float = 0.0
    max_transaction_limit_present: float = 0.0
    blacklist_function_present: float = 0.0

    # NETWORK / THREAT
    payment_graph_centrality: float = 0.0
    counterparty_avg_trust_score: float = 50.0
    incoming_tx_diversity_score: float = 0.0
    outgoing_tx_diversity_score: float = 0.0
    circular_payment_ratio: float = 0.0
    energy_drain_victim_count: float = 0.0
    phishing_contract_association_score: float = 0.0
    mixer_interaction_score: float = 0.0
    address_poisoning_attempts: float = 0.0
    permission_bypass_attempts: float = 0.0

    def to_numpy(self) -> np.ndarray:
        """Return features in canonical order as float32 array."""
        return np.array(
            [getattr(self, f) for f in AGENT_FEATURES],
            dtype=np.float32,
        )

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in AGENT_FEATURES}

    def clamp(self) -> "AgentFeatureVector":
        """Clamp all features to their valid bounds."""
        for name, (lo, hi) in FEATURE_BOUNDS.items():
            val = getattr(self, name)
            setattr(self, name, float(np.clip(val, lo, hi)))
        return self
