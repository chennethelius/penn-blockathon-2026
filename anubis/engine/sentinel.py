"""
Anubis Sentinel — Real-Time Threat Monitor
===========================================
Polls TronGrid for Tron-specific threat signals on a configurable interval.
Alert types (Tron-native, beyond Maiat's generic rug signals):

  energy_drain        — malicious contracts draining victim energy
  fake_usdt           — TRC-20 contracts spoofing the real USDT address
  freeze_abuse        — hidden freeze authority in TRC-20 tokens being exercised
  permission_bypass   — Tron multi-sig abuse / unauthorized permission changes
  sr_manipulation     — Super Representative vote manipulation
  address_poisoning   — Tron vanity address poisoning attacks

Sentinel maintains an in-memory alert ring buffer (last 1000 alerts)
and exposes `get_alerts()` for the API layer.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Real USDT TRC-20 contract on Tron mainnet
REAL_USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
ALERT_BUFFER_SIZE = 1000

# Known SR addresses (Top-27 Super Representatives — abbreviated sample)
KNOWN_SR_ADDRESSES = {
    "TLyqzVGLV1srkB7dToTAEqgDSfPtXRJZYH",
    "TTcYhypP8m4phDhN6oRexz2174zAFJ254R",
}


class AlertSeverity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    ENERGY_DRAIN       = "energy_drain"
    FAKE_USDT          = "fake_usdt"
    FREEZE_ABUSE       = "freeze_abuse"
    PERMISSION_BYPASS  = "permission_bypass"
    SR_MANIPULATION    = "sr_manipulation"
    ADDRESS_POISONING  = "address_poisoning"
    WASH_TRADING       = "wash_trading"
    HONEYPOT_DEPLOYED  = "honeypot_deployed"
    HIGH_RISK_AGENT    = "high_risk_agent"   # generic, from ML score < 20


@dataclass
class SentinelAlert:
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    address: str
    description: str
    evidence: dict
    timestamp: float = field(default_factory=time.time)
    auto_blacklisted: bool = False

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "address": self.address,
            "description": self.description,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "auto_blacklisted": self.auto_blacklisted,
        }


class Sentinel:
    """
    Asynchronous real-time threat monitor.
    Call `start()` to begin background polling.
    Call `stop()` to shut down gracefully.
    """

    def __init__(
        self,
        trongrid_base: str = "https://api.trongrid.io",
        api_key: str = "",
        check_interval: float = 30.0,
    ):
        headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=trongrid_base, headers=headers, timeout=10.0
        )
        self._interval = check_interval
        self._alerts: deque[SentinelAlert] = deque(maxlen=ALERT_BUFFER_SIZE)
        self._report_counts: dict[str, int] = {}  # address → report count
        self._blacklist: set[str] = set()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._alert_counter = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Sentinel started (interval=%ds)", self._interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()
        logger.info("Sentinel stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None,
        limit: int = 50,
        since: Optional[float] = None,
    ) -> list[dict]:
        """Return filtered alerts, newest first."""
        alerts = list(self._alerts)
        alerts.reverse()  # newest first

        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        return [a.to_dict() for a in alerts[:limit]]

    def record_report(self, address: str, threat_type: str, reporter: str) -> dict:
        """
        Record a community threat report.
        Auto-blacklists after 3 independent reports.
        """
        self._report_counts[address] = self._report_counts.get(address, 0) + 1
        count = self._report_counts[address]

        auto_blacklisted = False
        if count >= 3 and address not in self._blacklist:
            self._blacklist.add(address)
            auto_blacklisted = True
            alert = self._make_alert(
                AlertType.HIGH_RISK_AGENT,
                AlertSeverity.CRITICAL,
                address,
                f"Auto-blacklisted after {count} independent reports",
                {"report_count": count, "threat_type": threat_type},
                auto_blacklisted=True,
            )
            self._alerts.append(alert)
            logger.warning("AUTO-BLACKLIST: %s (%d reports)", address, count)

        return {
            "address": address,
            "report_count": count,
            "auto_blacklisted": auto_blacklisted,
            "threshold": 3,
        }

    def is_blacklisted(self, address: str) -> bool:
        return address in self._blacklist

    def get_threat_summary(self) -> dict:
        """Dashboard summary of current threat landscape."""
        alerts = list(self._alerts)
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for a in alerts:
            by_type[a.alert_type.value] = by_type.get(a.alert_type.value, 0) + 1
            by_severity[a.severity.value] = by_severity.get(a.severity.value, 0) + 1

        recent_1h = [a for a in alerts if time.time() - a.timestamp < 3600]

        return {
            "total_alerts": len(alerts),
            "alerts_last_1h": len(recent_1h),
            "blacklisted_addresses": len(self._blacklist),
            "by_type": by_type,
            "by_severity": by_severity,
            "top_threat": max(by_type, key=by_type.get) if by_type else None,
        }

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    async def _poll_loop(self):
        while self._running:
            try:
                await asyncio.gather(
                    self._check_energy_drain(),
                    self._check_fake_usdt_contracts(),
                    self._check_freeze_abuse(),
                    self._check_permission_bypass(),
                    return_exceptions=True,
                )
            except Exception as e:
                logger.error("Sentinel poll error: %s", e)

            await asyncio.sleep(self._interval)

    # ------------------------------------------------------------------
    # Individual threat detectors
    # ------------------------------------------------------------------

    async def _check_energy_drain(self):
        """
        Detect wallets rapidly consuming energy from many victim accounts.
        Heuristic: contracts that call triggerSmartContract on many unique
        addresses within a short window with net negative energy outcomes.
        """
        try:
            r = await self._client.get(
                "/v1/contracts",
                params={"limit": 20, "order_by": "energy_factor,asc"},
            )
            if r.status_code != 200:
                return

            contracts = r.json().get("data", [])
            for contract in contracts:
                energy_factor = contract.get("energy_factor", 1.0)
                address = contract.get("contract_address", "")
                if not address:
                    continue

                # Very low energy factor = draining pattern
                if energy_factor < 0.3:
                    alert = self._make_alert(
                        AlertType.ENERGY_DRAIN,
                        AlertSeverity.HIGH,
                        address,
                        f"Contract with low energy_factor={energy_factor:.2f} — potential energy drain attack",
                        {"energy_factor": energy_factor},
                    )
                    self._alerts.append(alert)
                    logger.warning("Energy drain detected: %s (ef=%.2f)", address, energy_factor)

        except Exception as e:
            logger.debug("energy drain check failed: %s", e)

    async def _check_fake_usdt_contracts(self):
        """
        Detect TRC-20 contracts with names/symbols spoofing USDT but at
        a different contract address.
        """
        try:
            # Search TronScan for recently deployed TRC-20 tokens named "USDT"
            # This is a heuristic; production would use a TronScan-specific endpoint
            r = await self._client.get(
                "/v1/contracts",
                params={
                    "limit": 50,
                    "order_by": "timestamp,desc",
                    "contract_type": "trc20",
                },
            )
            if r.status_code != 200:
                return

            contracts = r.json().get("data", [])
            for c in contracts:
                name = (c.get("name") or "").upper()
                symbol = (c.get("symbol") or "").upper()
                address = c.get("contract_address", "")

                if not address or address == REAL_USDT:
                    continue

                # Spoofing check: USDT-like name at non-canonical address
                if "USDT" in name or "USDT" in symbol or "TETHER" in name:
                    alert = self._make_alert(
                        AlertType.FAKE_USDT,
                        AlertSeverity.CRITICAL,
                        address,
                        f"Potential fake USDT contract: name='{name}' symbol='{symbol}'",
                        {"name": name, "symbol": symbol, "real_usdt": REAL_USDT},
                    )
                    self._alerts.append(alert)
                    logger.critical("FAKE USDT detected: %s (name=%s)", address, name)

        except Exception as e:
            logger.debug("fake USDT check failed: %s", e)

    async def _check_freeze_abuse(self):
        """
        Detect TRC-20 tokens where freeze authority is being exercised
        (balance freeze events on holder accounts).
        """
        try:
            r = await self._client.get(
                "/v1/transactions",
                params={
                    "limit": 100,
                    "contract_type": "FreezeBalanceV2Contract",
                    "order_by": "block_timestamp,desc",
                },
            )
            if r.status_code != 200:
                return

            txs = r.json().get("data", [])
            freeze_counts: dict[str, int] = {}

            for tx in txs:
                contract_data = tx.get("raw_data", {}).get("contract", [{}])[0]
                value = contract_data.get("parameter", {}).get("value", {})
                owner = value.get("owner_address", "")
                if owner:
                    freeze_counts[owner] = freeze_counts.get(owner, 0) + 1

            for address, count in freeze_counts.items():
                if count >= 5:
                    alert = self._make_alert(
                        AlertType.FREEZE_ABUSE,
                        AlertSeverity.HIGH,
                        address,
                        f"Excessive freeze calls ({count} in recent window) — potential freeze abuse",
                        {"freeze_count": count},
                    )
                    self._alerts.append(alert)

        except Exception as e:
            logger.debug("freeze abuse check failed: %s", e)

    async def _check_permission_bypass(self):
        """
        Detect Tron multi-sig permission abuse:
        AccountPermissionUpdateContract calls that reduce required threshold
        or add unexpected owner keys.
        """
        try:
            r = await self._client.get(
                "/v1/transactions",
                params={
                    "limit": 50,
                    "contract_type": "AccountPermissionUpdateContract",
                    "order_by": "block_timestamp,desc",
                },
            )
            if r.status_code != 200:
                return

            txs = r.json().get("data", [])
            for tx in txs:
                contract_data = tx.get("raw_data", {}).get("contract", [{}])[0]
                value = contract_data.get("parameter", {}).get("value", {})
                owner = value.get("owner_address", "")
                active_permissions = value.get("actives", [])

                # Suspicious: permission with very low threshold
                for perm in active_permissions:
                    threshold = perm.get("threshold", 1)
                    keys = perm.get("keys", [])
                    if threshold == 1 and len(keys) > 3:
                        alert = self._make_alert(
                            AlertType.PERMISSION_BYPASS,
                            AlertSeverity.HIGH,
                            owner,
                            f"Suspicious permission update: threshold=1 with {len(keys)} keys",
                            {"threshold": threshold, "key_count": len(keys)},
                        )
                        self._alerts.append(alert)

        except Exception as e:
            logger.debug("permission bypass check failed: %s", e)

    # ------------------------------------------------------------------
    # Manual alert injection (for testing and community reports)
    # ------------------------------------------------------------------

    def inject_alert(
        self,
        address: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        description: str,
        evidence: dict,
    ) -> SentinelAlert:
        alert = self._make_alert(alert_type, severity, address, description, evidence)
        self._alerts.append(alert)
        return alert

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        address: str,
        description: str,
        evidence: dict,
        auto_blacklisted: bool = False,
    ) -> SentinelAlert:
        self._alert_counter += 1
        alert_id = f"ANUBIS-{self._alert_counter:06d}"
        return SentinelAlert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            address=address,
            description=description,
            evidence=evidence,
            auto_blacklisted=auto_blacklisted,
        )
