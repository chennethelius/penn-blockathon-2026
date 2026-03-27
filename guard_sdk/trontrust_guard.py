"""
TronTrust Guard SDK
===================
Wraps a tronpy client with automatic trust checking before every transaction.

Install:
    pip install trontrust-guard

Usage:
    from trontrust_guard import TrustGuard

    guard = TrustGuard(private_key="your_hex_key", min_score=60)

    # Checks trust before sending — blocks if untrusted
    result = guard.send_trx("TRecipientAddress", 100)

    # Check without sending
    check = guard.check("TSomeAddress")

    # Adjust threshold
    guard.min_score = 80
"""

import httpx
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider


class TrustCheckFailed(Exception):
    """Raised when a recipient fails the trust check."""
    def __init__(self, address, score, min_score, flags):
        self.address = address
        self.score = score
        self.min_score = min_score
        self.flags = flags
        super().__init__(
            f"Recipient {address} blocked: trust score {score} < minimum {min_score}. "
            f"Flags: {', '.join(flags) if flags else 'none'}"
        )


class TrustGuard:
    """Trust-gated wallet wrapper for Tron."""

    def __init__(
        self,
        private_key: str,
        min_score: int = 60,
        api_url: str = "http://localhost:8000/api/v1",
        network: str = "nile",
        enforce: bool = True,
    ):
        """
        Args:
            private_key: Hex private key for the wallet
            min_score: Minimum trust score to allow transactions (0-100)
            api_url: TronTrust API base URL
            network: "nile", "shasta", or "mainnet"
            enforce: If False, logs warnings but doesn't block
        """
        networks = {
            "nile": "https://api.nileex.io",
            "shasta": "https://api.shasta.trongrid.io",
            "mainnet": "https://api.trongrid.io",
        }
        self._client = Tron(provider=HTTPProvider(networks.get(network, networks["nile"])))
        self._key = PrivateKey(bytes.fromhex(private_key))
        self.address = self._key.public_key.to_base58check_address()
        self.min_score = min_score
        self._api = api_url
        self.enforce = enforce

        # Stats
        self.total_checks = 0
        self.total_blocked = 0
        self.total_sent = 0

    def check(self, address: str) -> dict:
        """Check trust score for an address without sending.

        Returns:
            {
                "address": "T...",
                "score": 73,
                "verdict": "proceed",
                "flags": ["concentrated_holdings"],
                "would_pass": True,
                "min_required": 60
            }
        """
        self.total_checks += 1
        try:
            resp = httpx.get(f"{self._api}/agent/{address}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            score = data.get("trustScore", 0)
            return {
                "address": address,
                "score": score,
                "verdict": data.get("verdict", "unknown"),
                "flags": data.get("flags", []),
                "would_pass": score >= self.min_score,
                "min_required": self.min_score,
            }
        except Exception as e:
            # Fail open — never block because our API is down
            return {
                "address": address,
                "score": 50,
                "verdict": "caution",
                "flags": ["trontrust_unreachable"],
                "would_pass": True,
                "min_required": self.min_score,
                "error": str(e),
            }

    def send_trx(self, to: str, amount_trx: float) -> dict:
        """Send TRX with trust check. Blocks if recipient is untrusted.

        Args:
            to: Recipient Tron address
            amount_trx: Amount in TRX

        Returns:
            {"success": True, "tx_hash": "...", "score": 73} on success
            {"success": False, "error": "...", "score": 12} on block

        Raises:
            TrustCheckFailed: If enforce=True and recipient fails trust check
        """
        check = self.check(to)

        if not check["would_pass"]:
            self.total_blocked += 1
            if self.enforce:
                raise TrustCheckFailed(to, check["score"], self.min_score, check["flags"])
            return {
                "success": False,
                "error": f"Trust check failed: score {check['score']} < {self.min_score}",
                "score": check["score"],
                "flags": check["flags"],
            }

        # Trust check passed — execute transaction
        amount_sun = int(amount_trx * 1_000_000)
        txn = (
            self._client.trx.transfer(self.address, to, amount_sun)
            .build()
            .sign(self._key)
        )
        result = txn.broadcast()
        tx_hash = result.get("txid", "")

        self.total_sent += 1
        return {
            "success": True,
            "tx_hash": tx_hash,
            "amount_trx": amount_trx,
            "to": to,
            "score": check["score"],
            "verdict": check["verdict"],
        }

    def send_trc20(self, token_address: str, to: str, amount: int) -> dict:
        """Send TRC-20 tokens with trust check.

        Args:
            token_address: TRC-20 contract address
            to: Recipient address
            amount: Token amount in smallest unit (e.g. 6 decimals for USDT)
        """
        check = self.check(to)

        if not check["would_pass"]:
            self.total_blocked += 1
            if self.enforce:
                raise TrustCheckFailed(to, check["score"], self.min_score, check["flags"])
            return {
                "success": False,
                "error": f"Trust check failed: score {check['score']} < {self.min_score}",
                "score": check["score"],
            }

        contract = self._client.get_contract(token_address)
        txn = (
            contract.functions.transfer(to, amount)
            .with_owner(self.address)
            .fee_limit(30_000_000)
            .build()
            .sign(self._key)
        )
        result = txn.broadcast()

        self.total_sent += 1
        return {
            "success": True,
            "tx_hash": result.get("txid", ""),
            "to": to,
            "score": check["score"],
        }

    def stats(self) -> dict:
        """Get guard statistics."""
        return {
            "address": self.address,
            "min_score": self.min_score,
            "enforce": self.enforce,
            "total_checks": self.total_checks,
            "total_blocked": self.total_blocked,
            "total_sent": self.total_sent,
            "block_rate": f"{(self.total_blocked / max(self.total_checks, 1)) * 100:.1f}%",
        }
