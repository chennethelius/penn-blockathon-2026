"""On-chain contract interaction service via tronpy.

Wraps TronTrustOracle, TrustPassport, TrustGateContract, and CommercialTrust
with typed Python methods. All write operations are signed by the operator key.
"""

import os
import json
import logging
from pathlib import Path
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

logger = logging.getLogger(__name__)

NETWORK = os.getenv("TRON_NETWORK", "nile")
PRIVATE_KEY = os.getenv("PRIVATE_KEY_NILE", "")

NETWORK_URLS = {
    "nile": "https://api.nileex.io",
    "shasta": "https://api.shasta.trongrid.io",
    "mainnet": "https://api.trongrid.io",
}

# Contract addresses — set after deployment
ORACLE_ADDRESS = os.getenv("TRONTRUST_ORACLE_ADDRESS", "")
PASSPORT_ADDRESS = os.getenv("TRUST_PASSPORT_ADDRESS", "")
GATE_ADDRESS = os.getenv("TRUST_GATE_ADDRESS", "")
COMMERCIAL_ADDRESS = os.getenv("COMMERCIAL_TRUST_ADDRESS", "")
TRUST_WALLET_ADDRESS = os.getenv("TRUST_WALLET_ADDRESS", "")

# Verdict mapping: string → uint8 used in contracts
VERDICT_MAP = {
    "UNKNOWN": 0,
    "TRUSTED": 1,
    "REPUTABLE": 2,
    "CAUTION": 3,
    "RISKY": 4,
    "BLACKLISTED": 4,
}

# ABI fragments for the methods we call.
# tronpy uses these to encode/decode calls.
ORACLE_ABI = [
    {
        "name": "registerAgent",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_agentType", "type": "string"},
        ],
        "outputs": [],
    },
    {
        "name": "updateScore",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_score", "type": "uint8"},
            {"name": "_verdict", "type": "uint8"},
        ],
        "outputs": [],
    },
    {
        "name": "batchUpdateScores",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_agents", "type": "address[]"},
            {"name": "_scores", "type": "uint8[]"},
            {"name": "_verdicts", "type": "uint8[]"},
        ],
        "outputs": [],
    },
    {
        "name": "blacklist",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_reason", "type": "string"},
        ],
        "outputs": [],
    },
    {
        "name": "createAttestation",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_subject", "type": "address"},
            {"name": "_score", "type": "uint8"},
            {"name": "_evidenceCid", "type": "string"},
        ],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
    {
        "name": "getTrust",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_agent", "type": "address"}],
        "outputs": [
            {"name": "score", "type": "uint8"},
            {"name": "verdict", "type": "uint8"},
            {"name": "isTrustedBool", "type": "bool"},
        ],
    },
    {
        "name": "getAgentProfile",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_agent", "type": "address"}],
        "outputs": [
            {"name": "agentType", "type": "string"},
            {"name": "registeredAt", "type": "uint256"},
            {"name": "totalJobs", "type": "uint256"},
            {"name": "completedJobs", "type": "uint256"},
            {"name": "totalVolumeUsdt", "type": "uint256"},
            {"name": "exists", "type": "bool"},
        ],
    },
    {
        "name": "updateAgentStats",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_totalJobs", "type": "uint256"},
            {"name": "_completedJobs", "type": "uint256"},
            {"name": "_totalVolumeUsdt", "type": "uint256"},
        ],
        "outputs": [],
    },
]

PASSPORT_ABI = [
    {
        "name": "mint",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_agentType", "type": "string"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "updateScore",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_trustScore", "type": "uint8"},
            {"name": "_commercialScore", "type": "uint8"},
        ],
        "outputs": [],
    },
    {
        "name": "addSunPoints",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_agent", "type": "address"},
            {"name": "_points", "type": "uint32"},
        ],
        "outputs": [],
    },
    {
        "name": "getPassport",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_agent", "type": "address"}],
        "outputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "trustScore", "type": "uint8"},
            {"name": "commercialScore", "type": "uint8"},
            {"name": "agentType", "type": "string"},
            {"name": "registeredAt", "type": "uint256"},
            {"name": "sunPoints", "type": "uint32"},
        ],
    },
]

COMMERCIAL_ABI = [
    {
        "name": "recordInvoicePayment",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_payer", "type": "address"},
            {"name": "_payee", "type": "address"},
            {"name": "_amountUsdt", "type": "uint256"},
            {"name": "_daysToPayment", "type": "uint256"},
            {"name": "_wasOverdue", "type": "bool"},
        ],
        "outputs": [],
    },
    {
        "name": "getCommercialScore",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "_a", "type": "address"},
            {"name": "_b", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint8"}],
    },
    {
        "name": "getRecommendedTerms",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "_buyer", "type": "address"},
            {"name": "_merchant", "type": "address"},
        ],
        "outputs": [
            {"name": "paymentWindowDays", "type": "uint256"},
            {"name": "requiresEscrow", "type": "bool"},
            {"name": "creditLimitUsdt", "type": "uint256"},
        ],
    },
]

TRUST_WALLET_ABI = [
    {
        "name": "send",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_amount", "type": "uint256"},
        ],
        "outputs": [],
    },
    {
        "name": "sendToken",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_token", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_amount", "type": "uint256"},
        ],
        "outputs": [],
    },
    {
        "name": "setMinTrustScore",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "_newScore", "type": "uint8"}],
        "outputs": [],
    },
    {
        "name": "checkRecipient",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "_to", "type": "address"}],
        "outputs": [
            {"name": "score", "type": "uint8"},
            {"name": "wouldPass", "type": "bool"},
            {"name": "minRequired", "type": "uint8"},
        ],
    },
    {
        "name": "getStats",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "transfers", "type": "uint256"},
            {"name": "blocked", "type": "uint256"},
            {"name": "volumeTrx", "type": "uint256"},
            {"name": "currentMinScore", "type": "uint8"},
            {"name": "enforcing", "type": "bool"},
        ],
    },
    {
        "name": "minTrustScore",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
]


class TronTrustContracts:
    """Manages all TronTrust contract interactions."""

    def __init__(self):
        url = NETWORK_URLS.get(NETWORK, NETWORK_URLS["nile"])
        self._client = Tron(provider=HTTPProvider(url))
        self._priv_key = PrivateKey(bytes.fromhex(PRIVATE_KEY)) if PRIVATE_KEY else None
        self._operator = self._priv_key.public_key.to_base58check_address() if self._priv_key else None

        # Load contracts
        self._oracle = None
        self._passport = None
        self._commercial = None
        self._wallet = None

        if ORACLE_ADDRESS:
            self._oracle = self._client.get_contract(ORACLE_ADDRESS)
            self._oracle.abi = ORACLE_ABI
        if PASSPORT_ADDRESS:
            self._passport = self._client.get_contract(PASSPORT_ADDRESS)
            self._passport.abi = PASSPORT_ABI
        if COMMERCIAL_ADDRESS:
            self._commercial = self._client.get_contract(COMMERCIAL_ADDRESS)
            self._commercial.abi = COMMERCIAL_ABI
        if TRUST_WALLET_ADDRESS:
            self._wallet = self._client.get_contract(TRUST_WALLET_ADDRESS)
            self._wallet.abi = TRUST_WALLET_ABI

        self._ready = bool(self._oracle and self._priv_key)
        if self._ready:
            logger.info("TronTrust contracts loaded (oracle=%s, operator=%s)", ORACLE_ADDRESS, self._operator)
        else:
            logger.warning("TronTrust contracts not configured — on-chain writes disabled")

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Oracle reads
    # ------------------------------------------------------------------

    def get_trust(self, address: str) -> dict:
        if not self._oracle:
            return {"score": 0, "verdict": 0, "isTrusted": False, "on_chain": False}
        result = self._oracle.functions.getTrust(address)
        return {
            "score": result[0],
            "verdict": result[1],
            "isTrusted": result[2],
            "on_chain": True,
        }

    def get_agent_profile(self, address: str) -> dict:
        if not self._oracle:
            return {"exists": False, "on_chain": False}
        result = self._oracle.functions.getAgentProfile(address)
        return {
            "agentType": result[0],
            "registeredAt": result[1],
            "totalJobs": result[2],
            "completedJobs": result[3],
            "totalVolumeUsdt": result[4],
            "exists": result[5],
            "on_chain": True,
        }

    # ------------------------------------------------------------------
    # Oracle writes
    # ------------------------------------------------------------------

    def register_agent(self, agent_address: str, agent_type: str) -> str:
        if not self._ready:
            logger.warning("Cannot register agent — contracts not configured")
            return ""
        txn = (
            self._oracle.functions.registerAgent(agent_address, agent_type)
            .with_owner(self._operator)
            .fee_limit(100_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        tx_hash = result.get("txid", "")
        logger.info("registerAgent tx: %s", tx_hash)
        return tx_hash

    def update_score(self, agent_address: str, score: int, verdict_str: str) -> str:
        if not self._ready:
            return ""
        verdict_uint8 = VERDICT_MAP.get(verdict_str.upper(), 0)
        txn = (
            self._oracle.functions.updateScore(agent_address, score, verdict_uint8)
            .with_owner(self._operator)
            .fee_limit(100_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        tx_hash = result.get("txid", "")
        logger.info("updateScore tx: %s (addr=%s, score=%d)", tx_hash, agent_address, score)
        return tx_hash

    def batch_update_scores(self, agents: list[str], scores: list[int], verdicts: list[str]) -> str:
        if not self._ready:
            return ""
        verdict_uint8s = [VERDICT_MAP.get(v.upper(), 0) for v in verdicts]
        txn = (
            self._oracle.functions.batchUpdateScores(agents, scores, verdict_uint8s)
            .with_owner(self._operator)
            .fee_limit(200_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        return result.get("txid", "")

    def blacklist_agent(self, agent_address: str, reason: str) -> str:
        if not self._ready:
            return ""
        txn = (
            self._oracle.functions.blacklist(agent_address, reason)
            .with_owner(self._operator)
            .fee_limit(100_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        tx_hash = result.get("txid", "")
        logger.warning("blacklist tx: %s (addr=%s, reason=%s)", tx_hash, agent_address, reason)
        return tx_hash

    def create_attestation(self, subject: str, score: int, evidence_cid: str) -> str:
        if not self._ready:
            return ""
        txn = (
            self._oracle.functions.createAttestation(subject, score, evidence_cid)
            .with_owner(self._operator)
            .fee_limit(100_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        return result.get("txid", "")

    # ------------------------------------------------------------------
    # Passport
    # ------------------------------------------------------------------

    def mint_passport(self, to_address: str, agent_type: str) -> str:
        if not self._passport or not self._priv_key:
            return ""
        txn = (
            self._passport.functions.mint(to_address, agent_type)
            .with_owner(self._operator)
            .fee_limit(100_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        tx_hash = result.get("txid", "")
        logger.info("mint passport tx: %s (to=%s)", tx_hash, to_address)
        return tx_hash

    def update_passport_score(self, agent_address: str, trust_score: int, commercial_score: int) -> str:
        if not self._passport or not self._priv_key:
            return ""
        txn = (
            self._passport.functions.updateScore(agent_address, trust_score, commercial_score)
            .with_owner(self._operator)
            .fee_limit(100_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        return result.get("txid", "")

    def add_sun_points(self, agent_address: str, points: int) -> str:
        if not self._passport or not self._priv_key:
            return ""
        txn = (
            self._passport.functions.addSunPoints(agent_address, points)
            .with_owner(self._operator)
            .fee_limit(50_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        return result.get("txid", "")

    def get_passport(self, address: str) -> dict:
        if not self._passport:
            return {"exists": False, "on_chain": False}
        try:
            result = self._passport.functions.getPassport(address)
            return {
                "tokenId": result[0],
                "trustScore": result[1],
                "commercialScore": result[2],
                "agentType": result[3],
                "registeredAt": result[4],
                "sunPoints": result[5],
                "exists": True,
                "on_chain": True,
            }
        except Exception:
            return {"exists": False, "on_chain": True}

    # ------------------------------------------------------------------
    # Commercial Trust
    # ------------------------------------------------------------------

    def record_payment(self, payer: str, payee: str, amount_usdt: int, days: int, overdue: bool) -> str:
        if not self._commercial or not self._priv_key:
            return ""
        txn = (
            self._commercial.functions.recordInvoicePayment(payer, payee, amount_usdt, days, overdue)
            .with_owner(self._operator)
            .fee_limit(100_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        return result.get("txid", "")

    def get_commercial_score(self, a: str, b: str) -> int:
        if not self._commercial:
            return 50
        return self._commercial.functions.getCommercialScore(a, b)

    def get_recommended_terms(self, buyer: str, merchant: str) -> dict:
        if not self._commercial:
            return {"paymentWindowDays": 7, "requiresEscrow": True, "creditLimitUsdt": 5000}
        result = self._commercial.functions.getRecommendedTerms(buyer, merchant)
        return {
            "paymentWindowDays": result[0],
            "requiresEscrow": result[1],
            "creditLimitUsdt": result[2],
        }


    # ------------------------------------------------------------------
    # TrustWallet
    # ------------------------------------------------------------------

    def wallet_send(self, to: str, amount_sun: int) -> str:
        if not self._wallet or not self._priv_key:
            return ""
        txn = (
            self._wallet.functions.send(to, amount_sun)
            .with_owner(self._operator)
            .fee_limit(100_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        return result.get("txid", "")

    def wallet_set_min_trust(self, new_score: int) -> str:
        if not self._wallet or not self._priv_key:
            return ""
        txn = (
            self._wallet.functions.setMinTrustScore(new_score)
            .with_owner(self._operator)
            .fee_limit(50_000_000)
            .build()
            .sign(self._priv_key)
        )
        result = txn.broadcast()
        return result.get("txid", "")

    def wallet_check_recipient(self, to: str) -> dict:
        if not self._wallet:
            return {"score": 0, "wouldPass": False, "minRequired": 0}
        result = self._wallet.functions.checkRecipient(to)
        return {
            "score": result[0],
            "wouldPass": result[1],
            "minRequired": result[2],
        }

    def wallet_get_stats(self) -> dict:
        if not self._wallet:
            return {"transfers": 0, "blocked": 0, "volumeTrx": 0, "currentMinScore": 0, "enforcing": False}
        result = self._wallet.functions.getStats()
        return {
            "transfers": result[0],
            "blocked": result[1],
            "volumeTrx": result[2],
            "currentMinScore": result[3],
            "enforcing": result[4],
        }


# Singleton instance
_instance = None


def get_contracts() -> TronTrustContracts:
    global _instance
    if _instance is None:
        _instance = TronTrustContracts()
    return _instance
