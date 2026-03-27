"""
Bulk TRC-20 Token Data Collector
==================================
Fetches thousands of real TRC-20 tokens from TronScan's /contracts endpoint
and builds feature rows directly from the listing response — no per-token
API calls, no rate limiting.

The /contracts response already contains the key token health features:
  holders_count, issue_time, verify_status, risk flag, total_supply.

Labeling strategy:
  0 (safe)  — risk=False AND (holders > 1000 OR age > 180d OR verified)
  1 (risky) — risk=True OR (holders < 50 AND age < 30d AND unverified)
  -1        — uncertain; skipped

Usage:
    python3 scripts/collect_token_data.py
    python3 scripts/collect_token_data.py --max-tokens 5000
    python3 scripts/collect_token_data.py --resume
"""

import asyncio
import argparse
import csv
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pandas as pd
from dotenv import load_dotenv

from features.schema import AGENT_FEATURES

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("token_collector")

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "real" / "token_features.csv"
PAGE_SIZE   = 50
TRONSCAN_BASE = "https://apilist.tronscanapi.com/api"


# -----------------------------------------------------------------------
# Feature extraction from /contracts response
# -----------------------------------------------------------------------

def _parse_age_days(issue_time_str: str) -> float:
    """Parse TronScan issue_time string like '2019-04-16 12:41:20' → age in days."""
    if not issue_time_str:
        return 0.0
    try:
        dt = datetime.strptime(issue_time_str[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return max((datetime.now(timezone.utc) - dt).days, 0.0)
    except Exception:
        return 0.0


def extract_features_from_contract(contract: dict) -> dict:
    """
    Build a feature row from a single /contracts response item.
    Populates only the features available in the listing:
      - token_holder_count, token_age_days, audit_score (from verify_status)
      - mint_function_present, freeze_function_present (from trc20token level)
      - All other features default to 0 / neutral values
    """
    row = {f: 0.0 for f in AGENT_FEATURES}

    # Neutral defaults for unknown features
    row["top10_holder_concentration"] = 0.5
    row["counterparty_avg_trust_score"] = 50.0
    row["bandwidth_efficiency_ratio"] = 0.5

    trc20 = contract.get("trc20token") or {}

    # Token holder count
    try:
        row["token_holder_count"] = float(trc20.get("holders_count") or 0)
    except (ValueError, TypeError):
        pass

    # Token age
    row["token_age_days"] = _parse_age_days(trc20.get("issue_time", ""))

    # Audit score from verification
    verify = contract.get("verify_status") or 0
    try:
        row["audit_score"] = min(float(verify), 2.0)
    except (ValueError, TypeError):
        pass

    # Risk / phishing flags
    if contract.get("risk"):
        row["phishing_contract_association_score"] = 0.9

    # Tag-based signals
    tag1 = (contract.get("tag1") or "").lower()
    if any(w in tag1 for w in ("scam", "phish", "fake", "hack")):
        row["phishing_contract_association_score"] = 0.9
    if "honeypot" in tag1:
        row["honeypot_probability"] = 0.9

    return row


def auto_label(row: dict, risk_flagged: bool) -> int:
    """
    Return 0 (safe), 1 (risky), or -1 (uncertain).
    Uses only features available from the /contracts listing.
    """
    if risk_flagged or row.get("phishing_contract_association_score", 0) > 0.5:
        return 1

    holders   = row.get("token_holder_count", 0)
    age_days  = row.get("token_age_days", 0)
    audit     = row.get("audit_score", 0)
    honeypot  = row.get("honeypot_probability", 0)

    if honeypot > 0.7:
        return 1

    # Risky signals
    if holders == 0 and age_days > 0:
        return 1
    if holders < 50 and age_days < 60 and audit == 0 and age_days > 0:
        return 1
    if holders < 10 and age_days > 0:
        return 1

    # Safe signals
    if holders > 5000:
        return 0
    if holders > 1000 and age_days > 90:
        return 0
    if holders > 500 and age_days > 180:
        return 0
    if audit >= 1 and holders > 100 and age_days > 14:
        return 0
    if holders > 200 and age_days > 60:
        return 0
    if holders > 100 and age_days > 365:
        return 0

    return -1  # uncertain


# -----------------------------------------------------------------------
# TronScan fetcher
# -----------------------------------------------------------------------

async def fetch_contracts_page(client: httpx.AsyncClient, start: int, sort: str = "") -> list[dict]:
    try:
        params = {"limit": PAGE_SIZE, "start": start}
        if sort:
            params["sort"] = sort
        r = await client.get(
            f"{TRONSCAN_BASE}/contracts",
            params=params,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
        logger.warning("/contracts start=%d returned %d", start, r.status_code)
        return []
    except Exception as e:
        logger.warning("/contracts start=%d error: %s", start, e)
        return []


# -----------------------------------------------------------------------
# Main collection
# -----------------------------------------------------------------------

async def collect(
    max_tokens: int,
    output_path: Path,
    resume: bool,
    tronscan_api_key: str,
):
    # Load already-collected addresses for resume
    already_done: set[str] = set()
    if resume and output_path.exists():
        try:
            df_existing = pd.read_csv(output_path)
            already_done = set(df_existing["address"].dropna())
            logger.info("Resume: %d tokens already collected", len(already_done))
        except Exception as e:
            logger.warning("Could not read existing output: %s", e)

    all_columns = ["address"] + AGENT_FEATURES + ["label", "risk_flagged"]
    write_header = not output_path.exists() or output_path.stat().st_size == 0
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = {"TRON-PRO-API-KEY": tronscan_api_key} if tronscan_api_key else {}

    n_safe   = 0
    n_risky  = 0
    n_skip   = 0
    n_saved  = 0

    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns, extrasaction="ignore")
        if write_header:
            writer.writeheader()

        # Two passes with different sort orders to maximise unique contracts returned
        SORT_PASSES = ["", "-balance"]

        async with httpx.AsyncClient(
            base_url=TRONSCAN_BASE, headers=headers, timeout=20.0
        ) as client:
          for sort_order in SORT_PASSES:
            if n_saved >= max_tokens:
                break
            logger.info("Starting pass with sort=%r", sort_order or "default")
            for start in range(0, 10000, PAGE_SIZE):
                if n_saved >= max_tokens:
                    break

                page = await fetch_contracts_page(client, start, sort=sort_order)
                if not page:
                    logger.info("Empty page at start=%d sort=%r, stopping pass.", start, sort_order)
                    break

                for contract in page:
                    if n_saved >= max_tokens:
                        break

                    addr  = contract.get("address") or ""
                    trc20 = contract.get("trc20token")

                    # Skip non-TRC20 contracts and already-collected
                    if not (addr.startswith("T") and len(addr) == 34 and trc20):
                        continue
                    if addr in already_done:
                        continue

                    risk_flagged = bool(contract.get("risk"))
                    row = extract_features_from_contract(contract)
                    label = auto_label(row, risk_flagged)

                    if label == -1:
                        n_skip += 1
                        continue

                    row["address"]      = addr
                    row["label"]        = label
                    row["risk_flagged"] = int(risk_flagged)
                    writer.writerow(row)
                    f.flush()
                    already_done.add(addr)
                    n_saved += 1

                    if label == 0:
                        n_safe += 1
                    else:
                        n_risky += 1

                logger.info(
                    "start=%4d | saved=%d (safe=%d risky=%d skipped=%d)",
                    start, n_saved, n_safe, n_risky, n_skip,
                )
                await asyncio.sleep(0.3)

    return n_saved, n_safe, n_risky


async def main():
    parser = argparse.ArgumentParser(
        description="Collect real TRC-20 token features from TronScan for Anubis training"
    )
    parser.add_argument("--max-tokens", type=int, default=3000,
                        help="Number of labeled tokens to collect (default: 3000)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip tokens already in the output CSV")
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    args = parser.parse_args()

    tronscan_key = os.getenv("TRONSCAN_API_KEY", "")
    if not tronscan_key:
        logger.warning("TRONSCAN_API_KEY not set — may hit rate limits")

    output_path = Path(args.output)
    logger.info("Collecting up to %d labeled tokens → %s", args.max_tokens, output_path)

    start_time = time.time()
    n_saved, n_safe, n_risky = await collect(
        max_tokens=args.max_tokens,
        output_path=output_path,
        resume=args.resume,
        tronscan_api_key=tronscan_key,
    )
    elapsed = time.time() - start_time

    logger.info(
        "Done: %d tokens saved in %.1fs | safe=%d risky=%d",
        n_saved, elapsed, n_safe, n_risky,
    )
    if n_saved > 0:
        logger.info(
            "\nNext step:\n"
            "  python scripts/retrain_on_real_data.py "
            "--data-path %s --real-only --eval",
            output_path,
        )


if __name__ == "__main__":
    asyncio.run(main())
