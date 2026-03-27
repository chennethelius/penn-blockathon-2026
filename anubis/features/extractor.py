"""
TronGrid / TronScan feature extractor.

All data is pulled from:
  - TronGrid  (account info, balances, energy/bandwidth)
  - TronScan  (tx history, contract deployments, DEX trades, lending, risk flags)

JustLend and SunSwap do not have stable public REST APIs — TronScan indexes
both protocols and exposes the data we need through its aggregated endpoints.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from features.schema import AgentFeatureVector

logger = logging.getLogger(__name__)

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# Documented mixer/tumbler addresses on Tron
KNOWN_MIXERS = {
    "TYASr5UV6HEcXatwdFyffSCMSi6cS1JjcC",
    "TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7",
}

# JustLend cToken contract addresses (the ones that emit Borrow/Repay events)
JUSTLEND_MARKETS = {
    "TRC-USDT": "TX7kybeP6UwTBRHLNPYmswFESHfyjm9bAS",
    "TRC-TRX":  "TGjYzgCyPobsNS9n6WcbdLVR9dH7mWqFx4",
    "TRC-USDC": "TXDzbCCAbmyBKFqGEHBsRqPmLzn9v4ANNY",
}


class TronFeatureExtractor:
    """
    Pulls on-chain data and computes the 50 Anubis features.
    All network calls are async. Any individual failure returns safe defaults.
    """

    def __init__(
        self,
        trongrid_base: str = "https://api.trongrid.io",
        tronscan_base: str = "https://apilist.tronscanapi.com/api",
        api_key: str = "",
        tronscan_api_key: str = "",
        timeout: float = 20.0,
    ):
        tg_headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
        ts_headers = {"TRON-PRO-API-KEY": tronscan_api_key} if tronscan_api_key else {}
        self._tg = httpx.AsyncClient(
            base_url=trongrid_base, headers=tg_headers, timeout=timeout
        )
        self._ts = httpx.AsyncClient(base_url=tronscan_base, headers=ts_headers, timeout=timeout)

    async def close(self):
        await asyncio.gather(self._tg.aclose(), self._ts.aclose())

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def extract(self, address: str) -> AgentFeatureVector:
        fv = AgentFeatureVector(address=address)

        results = await asyncio.gather(
            self._fetch_account(address),
            self._fetch_tx_stats(address),
            self._fetch_trc20_transfers(address),
            self._fetch_dex_trades(address),
            self._fetch_justlend_via_tronscan(address),
            self._fetch_contract_deployments(address),
            self._fetch_tronscan_risk(address),
            return_exceptions=True,
        )

        (
            account_data,
            tx_stats,
            trc20_transfers,
            dex_trades,
            jl_data,
            contract_data,
            risk_data,
        ) = results

        self._apply_account(fv, account_data)
        self._apply_tx_stats(fv, tx_stats)
        self._apply_trc20_transfers(fv, trc20_transfers)
        self._apply_dex_trades(fv, dex_trades)
        self._apply_justlend(fv, jl_data)
        self._apply_contracts(fv, contract_data)
        self._apply_risk_flags(fv, risk_data)
        self._compute_network_features(fv, tx_stats)

        fv.clamp()
        return fv

    # ------------------------------------------------------------------
    # Fetchers
    # ------------------------------------------------------------------

    async def _fetch_account(self, address: str) -> dict:
        """TronGrid: account balance, TRC-20 holdings, creation time."""
        try:
            r = await self._tg.get(f"/v1/accounts/{address}")
            r.raise_for_status()
            data = r.json().get("data", [])
            return data[0] if data else {}
        except Exception as e:
            logger.warning("account fetch failed %s: %s", address, e)
            return {}

    async def _fetch_tx_stats(self, address: str) -> dict:
        """
        TronScan: transaction counts (total, 30d, 7d) and a 200-tx sample
        for counterparty and pattern analysis.
        """
        try:
            now = int(datetime.now(timezone.utc).timestamp() * 1000)
            ms_30d = now - 30 * 86_400_000
            ms_7d  = now - 7  * 86_400_000

            total_r, r30_r, r7_r, sample_r = await asyncio.gather(
                self._ts.get("transaction", params={
                    "address": address, "limit": 1, "count": "true",
                }),
                self._ts.get("transaction", params={
                    "address": address, "limit": 1, "count": "true",
                    "start_timestamp": ms_30d, "end_timestamp": now,
                }),
                self._ts.get("transaction", params={
                    "address": address, "limit": 1, "count": "true",
                    "start_timestamp": ms_7d, "end_timestamp": now,
                }),
                self._ts.get("transaction", params={
                    "address": address, "limit": 200, "sort": "-timestamp",
                }),
                return_exceptions=True,
            )

            def safe_total(r) -> int:
                if isinstance(r, Exception) or r.status_code != 200:
                    return 0
                return r.json().get("total", 0)

            sample = []
            if not isinstance(sample_r, Exception) and sample_r.status_code == 200:
                sample = sample_r.json().get("data", [])

            return {
                "total":   safe_total(total_r),
                "cnt_30d": safe_total(r30_r),
                "cnt_7d":  safe_total(r7_r),
                "sample":  sample,
            }
        except Exception as e:
            logger.warning("tx_stats failed %s: %s", address, e)
            return {"total": 0, "cnt_30d": 0, "cnt_7d": 0, "sample": []}

    async def _fetch_trc20_transfers(self, address: str) -> dict:
        """
        TronScan: TRC-20 transfer history.
        Used for USDT payment reliability, velocity, counterparty diversity.
        """
        try:
            r = await self._ts.get(
                "token_trc20/transfers",
                params={
                    "address": address,
                    "limit": 200,
                    "sort": "-timestamp",
                    "count": "true",
                },
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning("trc20 transfers failed %s: %s", address, e)
            return {}

    async def _fetch_dex_trades(self, address: str) -> dict:
        """
        TronScan: DEX trade history (SunSwap, JustSwap).
        Used for wash trading detection and LP manipulation scoring.
        """
        try:
            r = await self._ts.get(
                "exchange/transaction",
                params={
                    "address": address,
                    "limit": 200,
                    "sort": "-timestamp",
                },
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning("dex trades failed %s: %s", address, e)
            return {}

    async def _fetch_justlend_via_tronscan(self, address: str) -> dict:
        """
        TronScan: JustLend borrow/repay events indexed by TronScan.
        Endpoint: /api/contracts/event-logs filtered by JustLend contract topics.
        Falls back to TRC-20 transfer analysis vs JustLend market addresses.
        """
        try:
            # Query TRC-20 transfers to/from JustLend market contracts
            jl_addresses = list(JUSTLEND_MARKETS.values())
            borrowed = 0.0
            repaid   = 0.0

            for market_addr in jl_addresses:
                # Transfers FROM address TO JustLend market = supply/repay
                r_out = await self._ts.get(
                    "token_trc20/transfers",
                    params={
                        "address": address,
                        "toAddress": market_addr,
                        "limit": 200,
                        "count": "true",
                    },
                )
                # Transfers FROM JustLend TO address = borrow
                r_in = await self._ts.get(
                    "token_trc20/transfers",
                    params={
                        "address": address,
                        "fromAddress": market_addr,
                        "limit": 200,
                        "count": "true",
                    },
                )

                if r_in.status_code == 200:
                    for tx in r_in.json().get("token_transfers", []):
                        try:
                            borrowed += float(tx.get("quant", 0)) / 1e6
                        except (ValueError, TypeError):
                            pass

                if r_out.status_code == 200:
                    for tx in r_out.json().get("token_transfers", []):
                        try:
                            repaid += float(tx.get("quant", 0)) / 1e6
                        except (ValueError, TypeError):
                            pass

            return {"borrowed": borrowed, "repaid": repaid}
        except Exception as e:
            logger.warning("justlend fetch failed %s: %s", address, e)
            return {}

    async def _fetch_contract_deployments(self, address: str) -> dict:
        """TronScan: contracts deployed by this address."""
        try:
            r = await self._ts.get(
                "contracts",
                params={"creator": address, "limit": 50, "count": "true"},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning("contract deployments failed %s: %s", address, e)
            return {}

    async def _fetch_tronscan_risk(self, address: str) -> dict:
        """
        TronScan risk tag API — returns known scam/phishing flags.
        Endpoint: /api/account/risk  (documented in TronScan API v2)
        """
        try:
            r = await self._ts.get("account/risk", params={"address": address})
            if r.status_code == 200:
                return r.json()
            # Fallback: check account tags
            r2 = await self._ts.get("accountv2", params={"address": address})
            if r2.status_code == 200:
                return {"tags": r2.json().get("tags", [])}
            return {}
        except Exception as e:
            logger.warning("risk fetch failed %s: %s", address, e)
            return {}

    # ------------------------------------------------------------------
    # Feature appliers
    # ------------------------------------------------------------------

    def _apply_account(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        # Wallet age
        create_ms = data.get("create_time", 0)
        if create_ms:
            fv.wallet_age_days = (
                datetime.now(timezone.utc).timestamp() * 1000 - create_ms
            ) / 86_400_000

        # TRX balance (sun → TRX)
        fv.trx_balance_current = float(data.get("balance", 0)) / 1_000_000

        # USDT balance + token diversity
        trc20_list = data.get("trc20", [])
        fv.trc20_token_diversity = float(len(trc20_list))
        for tok in trc20_list:
            if isinstance(tok, dict) and USDT_CONTRACT in tok:
                try:
                    fv.usdt_balance_current = float(tok[USDT_CONTRACT]) / 1_000_000
                except (ValueError, TypeError):
                    pass

        # Energy / bandwidth from account resource data
        resources = data.get("account_resource", {})
        energy_limit = resources.get("energy_limit", 0)
        energy_used  = resources.get("energy_usage", 0)
        bw_limit     = data.get("free_net_limit", 0) + resources.get("net_limit", 0)
        bw_used      = data.get("net_usage", 0)

        fv.energy_usage_pattern = 1.0 if energy_limit > 0 and energy_used > 0 else 0.0
        if bw_limit > 0:
            fv.bandwidth_efficiency_ratio = min(bw_used / bw_limit, 1.0)

    def _apply_tx_stats(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        fv.tx_count_total = float(data["total"])
        fv.tx_count_30d   = float(data["cnt_30d"])
        fv.tx_count_7d    = float(data["cnt_7d"])

        sample: list = data.get("sample", [])
        if not sample:
            return

        now_ms = datetime.now(timezone.utc).timestamp() * 1000
        counterparties = set()
        contract_calls = 0
        usdt_txs = 0
        total_val = 0.0
        max_val   = 0.0

        for tx in sample:
            other = tx.get("toAddress") or tx.get("contractData", {}).get("to_address", "")
            if other and other != fv.address:
                counterparties.add(other)

            ct = tx.get("contractType", 0)
            if ct == 31:
                contract_calls += 1

            # USDT transfer value
            cd = tx.get("contractData", {})
            if cd.get("contract_address") == USDT_CONTRACT:
                usdt_txs += 1
                try:
                    amt = float(cd.get("amount", 0)) / 1_000_000
                    total_val += amt
                    max_val = max(max_val, amt)
                except (ValueError, TypeError):
                    pass

        n = len(sample)
        fv.unique_counterparties_total = float(len(counterparties))
        fv.unique_counterparties_30d   = float(len(counterparties))  # sample approx
        fv.usdt_tx_ratio               = usdt_txs / n if n > 0 else 0.0
        fv.contract_interaction_ratio  = contract_calls / n if n > 0 else 0.0
        fv.avg_tx_value_usdt           = total_val / max(usdt_txs, 1)
        fv.max_tx_value_usdt           = max_val

        if sample:
            last_ts = sample[0].get("timestamp", now_ms)
            fv.days_since_last_tx = (now_ms - last_ts) / 86_400_000

    def _apply_trc20_transfers(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        transfers = data.get("token_transfers", [])
        if not transfers:
            return

        usdt_transfers = [
            t for t in transfers
            if t.get("contract_address") == USDT_CONTRACT
        ]

        if usdt_transfers:
            # Payment reliability: ratio of outgoing USDT that came back (circular)
            sent_to: dict[str, float] = {}
            received_from: dict[str, float] = {}

            for t in usdt_transfers:
                try:
                    amt = float(t.get("quant", 0)) / 1_000_000
                except (ValueError, TypeError):
                    amt = 0.0

                frm = t.get("from_address", "")
                to  = t.get("to_address", "")

                if frm == fv.address:
                    sent_to[to] = sent_to.get(to, 0.0) + amt
                elif to == fv.address:
                    received_from[frm] = received_from.get(frm, 0.0) + amt

            # Invoice/commercial on-time rate: heuristic
            # wallets with many unique outgoing USDT counterparties + receipts = payment reliability
            if sent_to:
                received_back = {k for k in sent_to if k in received_from}
                fv.commercial_payment_on_time_rate = min(
                    len(received_back) / len(sent_to), 1.0
                )
                fv.invoice_completion_rate = fv.commercial_payment_on_time_rate

    def _apply_dex_trades(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        trades = data.get("data", [])
        if not trades:
            return

        fv.sunswap_trade_frequency = float(len(trades))

        # Wash trading: trades where from == to (same address both sides)
        self_trades = sum(
            1 for t in trades
            if t.get("maker") == fv.address and t.get("taker") == fv.address
        )
        fv.sunswap_wash_trading_score = self_trades / len(trades)

        # LP manipulation: rapid add→remove liquidity cycles
        lp_actions = [
            t for t in trades
            if t.get("type") in ("add_liquidity", "remove_liquidity", 2, 3)
        ]
        rapid = 0
        for i in range(1, len(lp_actions)):
            delta_ms = abs(
                lp_actions[i].get("timestamp", 0) - lp_actions[i-1].get("timestamp", 0)
            )
            if delta_ms < 3_600_000:  # < 1 hour
                rapid += 1
        fv.lp_manipulation_score = min(rapid / max(len(lp_actions), 1), 1.0)

    def _apply_justlend(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        borrowed = data.get("borrowed", 0.0)
        repaid   = data.get("repaid", 0.0)
        fv.justlend_total_borrowed_usdt = borrowed
        fv.justlend_total_repaid_usdt   = repaid
        if borrowed > 0:
            fv.justlend_repayment_rate = min(repaid / borrowed, 1.0)

    def _apply_contracts(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        fv.smart_contract_deployments = float(data.get("total", 0))
        contracts = data.get("data", [])
        audited = sum(1 for c in contracts if c.get("verified") or c.get("isVerify"))
        fv.audit_score = float(min(audited, 2))

    def _apply_risk_flags(self, fv: AgentFeatureVector, data):
        """
        TronScan risk tags map directly to threat features.
        Tag meanings: https://docs.tronscan.org/#account-risk
        """
        if not data or isinstance(data, Exception):
            return

        tags = data.get("tags", [])
        tag_names = {
            (t.get("tagName") or t.get("name") or "").lower()
            for t in tags
        }

        if any("phish" in t or "scam" in t for t in tag_names):
            fv.phishing_contract_association_score = 0.9
        if any("mixer" in t or "tornado" in t for t in tag_names):
            fv.mixer_interaction_score = 0.8
        if any("hack" in t or "exploit" in t for t in tag_names):
            fv.energy_drain_victim_count = max(fv.energy_drain_victim_count, 10.0)

    def _compute_network_features(self, fv: AgentFeatureVector, tx_stats):
        if not tx_stats or isinstance(tx_stats, Exception):
            return

        sample = tx_stats.get("sample", [])
        if not sample:
            return

        incoming: list[str] = []
        outgoing: list[str] = []

        for tx in sample:
            frm = tx.get("fromAddress", "")
            to  = tx.get("toAddress", "") or tx.get("contractData", {}).get("to_address", "")

            if frm == fv.address:
                outgoing.append(to)
            elif to == fv.address:
                incoming.append(frm)

            # Mixer check
            if frm in KNOWN_MIXERS or to in KNOWN_MIXERS:
                fv.mixer_interaction_score = min(fv.mixer_interaction_score + 0.1, 1.0)

        in_set  = set(incoming)
        out_set = set(outgoing)
        total   = len(in_set) + len(out_set) or 1

        fv.incoming_tx_diversity_score = min(len(in_set)  / total, 1.0)
        fv.outgoing_tx_diversity_score = min(len(out_set) / total, 1.0)
        fv.circular_payment_ratio      = min(len(in_set & out_set) / max(len(out_set), 1), 1.0)
        fv.payment_graph_centrality    = min((len(in_set) + len(out_set)) / 1000.0, 1.0)

    # ------------------------------------------------------------------
    # Token-centric extraction
    # ------------------------------------------------------------------

    async def extract_token(self, token_address: str) -> AgentFeatureVector:
        """
        Token-centric feature extraction for TRC-20 contract addresses.
        Populates all 50 features:
          - TOKEN HEALTH (25-39): from token contract metadata, holder distribution,
            liquidity/DEX data, and ABI function flags.
          - BEHAVIORAL (0-24): from the token contract's own transaction patterns
            AND from the deployer wallet's history (whichever yields more signal).
          - NETWORK/THREAT (40-49): from contract/deployer network patterns.

        This is the primary path when training on token data.
        """
        fv = AgentFeatureVector(address=token_address)

        # Fetch token-specific data in parallel
        token_info, holders_data, contract_data, dex_data, risk_data = await asyncio.gather(
            self._fetch_token_info(token_address),
            self._fetch_token_holders(token_address),
            self._fetch_token_contract(token_address),
            self._fetch_token_dex(token_address),
            self._fetch_tronscan_risk(token_address),
            return_exceptions=True,
        )

        self._apply_token_info(fv, token_info)
        self._apply_token_holders(fv, holders_data)
        self._apply_token_contract(fv, contract_data)
        self._apply_token_dex(fv, dex_data)
        self._apply_risk_flags(fv, risk_data)

        # Use deployer wallet for behavioral features if we can find it
        deployer = None
        if not isinstance(contract_data, Exception) and contract_data:
            deployer = (
                contract_data.get("creator")
                or contract_data.get("ownerAddress")
                or contract_data.get("owner_address")
            )

        behavioral_address = deployer if deployer else token_address

        account_data, tx_stats, trc20_transfers, dex_trades, jl_data = await asyncio.gather(
            self._fetch_account(behavioral_address),
            self._fetch_tx_stats(behavioral_address),
            self._fetch_trc20_transfers(behavioral_address),
            self._fetch_dex_trades(behavioral_address),
            self._fetch_justlend_via_tronscan(behavioral_address),
            return_exceptions=True,
        )

        self._apply_account(fv, account_data)
        self._apply_tx_stats(fv, tx_stats)
        self._apply_trc20_transfers(fv, trc20_transfers)
        self._apply_dex_trades(fv, dex_trades)
        self._apply_justlend(fv, jl_data)
        self._compute_network_features(fv, tx_stats)

        fv.clamp()
        return fv

    # ------------------------------------------------------------------
    # Token-specific fetchers
    # ------------------------------------------------------------------

    async def _fetch_token_info(self, token_address: str) -> dict:
        """
        TronScan: TRC-20 token metadata.
        Returns holder count, issue time, name, symbol, total supply.
        """
        try:
            r = await self._ts.get(
                "token_trc20",
                params={"contract": token_address, "showAll": 1},
            )
            if r.status_code == 200:
                data = r.json()
                # TronScan wraps results in trc20_tokens list
                tokens = data.get("trc20_tokens") or data.get("data", [])
                if isinstance(tokens, list) and tokens:
                    return tokens[0]
                if isinstance(data, dict) and data.get("contractAddress"):
                    return data
            return {}
        except Exception as e:
            logger.warning("token info failed %s: %s", token_address, e)
            return {}

    async def _fetch_token_holders(self, token_address: str) -> dict:
        """
        TronScan: top-10 token holders for concentration analysis.
        Also returns total holder count as a cross-check.
        """
        try:
            r = await self._ts.get(
                "tokenholders",
                params={
                    "address": token_address,
                    "limit": 10,
                },
            )
            if r.status_code == 200:
                return r.json()
            return {}
        except Exception as e:
            logger.warning("token holders failed %s: %s", token_address, e)
            return {}

    async def _fetch_token_contract(self, token_address: str) -> dict:
        """
        TronScan: contract metadata.
        Returns creator, verified status, and ABI (for function flag detection).
        """
        try:
            r = await self._ts.get(
                "contracts",
                params={"contract": token_address, "limit": 1},
            )
            if r.status_code == 200:
                data = r.json()
                contracts = data.get("data", [])
                return contracts[0] if contracts else {}
            return {}
        except Exception as e:
            logger.warning("contract info failed %s: %s", token_address, e)
            return {}

    async def _fetch_token_dex(self, token_address: str) -> dict:
        """
        TronScan: DEX/market data for the token.
        Returns liquidity, 24h volume, price, and exchange listing count.
        """
        try:
            # Token market stats from TronScan
            r = await self._ts.get(
                "token/market",
                params={"contract": token_address},
            )
            market_data: dict = {}
            if r.status_code == 200:
                market_data = r.json()

            # Fallback: exchange listings count
            r2 = await self._ts.get(
                "exchange",
                params={"token": token_address, "limit": 20, "count": "true"},
            )
            exchange_count = 0
            if r2.status_code == 200:
                exchange_count = r2.json().get("total", 0)

            market_data["dex_listing_count"] = exchange_count
            return market_data
        except Exception as e:
            logger.warning("token dex data failed %s: %s", token_address, e)
            return {}

    # ------------------------------------------------------------------
    # Token-specific appliers
    # ------------------------------------------------------------------

    def _apply_token_info(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        # Holder count — try multiple field names TronScan uses
        holder_count = (
            data.get("holders_count")
            or data.get("holders")
            or data.get("holder_count")
            or data.get("holdersCount")
            or 0
        )
        try:
            fv.token_holder_count = float(holder_count)
        except (ValueError, TypeError):
            pass

        # Token age from issue/creation time
        issue_time = (
            data.get("issue_time")
            or data.get("issueTime")
            or data.get("dateCreated")
            or data.get("date_created")
        )
        if issue_time:
            try:
                # TronScan returns ms timestamps or ISO date strings
                if isinstance(issue_time, (int, float)) and issue_time > 1e10:
                    age_days = (
                        datetime.now(timezone.utc).timestamp() * 1000 - float(issue_time)
                    ) / 86_400_000
                elif isinstance(issue_time, str) and "-" in issue_time:
                    from datetime import datetime as dt
                    issued = dt.strptime(issue_time[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    age_days = (datetime.now(timezone.utc) - issued).days
                else:
                    age_days = 0.0
                fv.token_age_days = max(age_days, 0.0)
            except Exception:
                pass

        # Total supply — use as a proxy for token diversity (not a direct feature,
        # but high supply with few holders → concentration signal)
        total_supply = data.get("total_supply") or data.get("totalSupply") or 0
        try:
            fv._token_total_supply = float(str(total_supply).replace(",", "")) or 1.0
        except (ValueError, TypeError, AttributeError):
            fv._token_total_supply = 1.0  # type: ignore[attr-defined]

    def _apply_token_holders(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        holders = data.get("data") or data.get("trc20_holders") or []
        total_from_api = data.get("total") or data.get("holderCount") or 0

        # Override holder count if more accurate value available
        if total_from_api:
            fv.token_holder_count = max(fv.token_holder_count, float(total_from_api))

        if not holders:
            return

        total_supply = getattr(fv, "_token_total_supply", 1.0) or 1.0  # type: ignore[attr-defined]

        # Compute top-10 concentration
        top10_balance = 0.0
        for h in holders[:10]:
            bal = h.get("balance") or h.get("quantity") or 0
            try:
                top10_balance += float(str(bal).replace(",", ""))
            except (ValueError, TypeError):
                pass

        if total_supply > 0 and top10_balance > 0:
            fv.top10_holder_concentration = min(top10_balance / total_supply, 1.0)

    def _apply_token_contract(self, fv: AgentFeatureVector, data):
        """
        Extract ABI function flags and verification status.
        TronScan includes ABI JSON for verified contracts — we scan it for
        freeze, mint, blacklist, and max-tx function signatures.
        """
        if not data or isinstance(data, Exception):
            return

        # Verified = at least community-audited
        verify_status = data.get("verify_status") or 0
        verified = data.get("verified") or data.get("isVerify") or verify_status >= 1
        if verified:
            fv.audit_score = max(fv.audit_score, min(float(verify_status), 2.0) if verify_status else 1.0)

        # Pull holder count + issue time from trc20token nested object
        trc20 = data.get("trc20token") or {}
        if trc20:
            holders = trc20.get("holders_count") or 0
            try:
                holders = float(holders)
                if holders > fv.token_holder_count:
                    fv.token_holder_count = holders
            except (ValueError, TypeError):
                pass

            issue_time = trc20.get("issue_time", "")
            if issue_time and fv.token_age_days == 0.0:
                from datetime import datetime as _dt
                try:
                    issued = _dt.strptime(issue_time[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    fv.token_age_days = max((datetime.now(timezone.utc) - issued).days, 0.0)
                except Exception:
                    pass

            # Derive top10 concentration heuristic when tokenholders endpoint fails:
            # more holders = less likely to be concentrated
            if fv.top10_holder_concentration == 1.0 and fv.token_holder_count > 0:
                h = fv.token_holder_count
                if h > 1_000_000:
                    fv.top10_holder_concentration = 0.15
                elif h > 100_000:
                    fv.top10_holder_concentration = 0.25
                elif h > 10_000:
                    fv.top10_holder_concentration = 0.40
                elif h > 1_000:
                    fv.top10_holder_concentration = 0.55
                elif h > 100:
                    fv.top10_holder_concentration = 0.70
                else:
                    fv.top10_holder_concentration = 0.90

        # Scan ABI for dangerous function signatures
        abi_raw = data.get("abi") or data.get("abiCode") or ""
        if isinstance(abi_raw, str) and abi_raw.strip().startswith("["):
            try:
                import json as _json
                abi = _json.loads(abi_raw)
                fn_names = {
                    (fn.get("name") or "").lower()
                    for fn in abi
                    if fn.get("type") in ("function", None)
                }
                if any("freeze" in n or "lock" in n for n in fn_names):
                    fv.freeze_function_present = 1.0
                if any("mint" in n or "issue" in n for n in fn_names):
                    fv.mint_function_present = 1.0
                if any("blacklist" in n or "ban" in n or "block" in n for n in fn_names):
                    fv.blacklist_function_present = 1.0
                if any("maxtx" in n or "maxamount" in n or "limit" in n for n in fn_names):
                    fv.max_transaction_limit_present = 1.0
                # Owner renounce: look for zero-address owner or renounce function
                if any("renounce" in n or "renouncedowner" in n for n in fn_names):
                    # Presence of renounce function + not a freeze token = likely renounced
                    fv.owner_renounced = 0.5  # partial signal; will be confirmed by ownership check
            except Exception:
                pass

        # Tag-based signals (TronScan applies tags to known-bad contracts)
        tags = data.get("tags") or []
        tag_names = {(t.get("tagName") or t.get("name") or "").lower() for t in tags}
        if any("honeypot" in t or "scam" in t or "fake" in t for t in tag_names):
            fv.honeypot_probability = max(fv.honeypot_probability, 0.85)
        if any("phish" in t for t in tag_names):
            fv.phishing_contract_association_score = max(
                fv.phishing_contract_association_score, 0.9
            )

    def _apply_token_dex(self, fv: AgentFeatureVector, data):
        if not data or isinstance(data, Exception):
            return

        # Liquidity (USD)
        liquidity = (
            data.get("liquidity")
            or data.get("liquidityUsd")
            or data.get("totalLiquidity")
            or 0
        )
        try:
            fv.token_liquidity_usd = float(liquidity)
        except (ValueError, TypeError):
            pass

        # Volume / liquidity ratio
        volume_24h = data.get("volume24h") or data.get("volume") or 0
        try:
            vol = float(volume_24h)
            liq = fv.token_liquidity_usd
            if liq > 0:
                fv.volume_to_liquidity_ratio = min(vol / liq, 50.0)
        except (ValueError, TypeError):
            pass

        # Price volatility proxy: use 24h price change %
        price_change = data.get("priceChange") or data.get("price_change_24h") or 0
        try:
            fv.price_volatility_7d = min(abs(float(price_change)) * 100, 100.0)
        except (ValueError, TypeError):
            pass

        # DEX listings count
        listing_count = data.get("dex_listing_count") or data.get("exchangeCount") or 0
        try:
            fv.dex_listings_count = float(listing_count)
        except (ValueError, TypeError):
            pass
