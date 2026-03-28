"""
Seed agents on Nile testnet with varied trust scores.
Run once to populate the dashboard and passport pages.

Usage:
    cd backend && python ../scripts/seed_agents.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.services.contracts import get_contracts

AGENTS = [
    # (address, agentType, trustScore, verdict)
    # Using real Tron mainnet addresses so TronGrid has data for them
    ("TX5ug3U97zsLdaNTfS5d89WJXTbvthjYPq", "DeFi Bot", 72, "REPUTABLE"),
    ("TLyqzVGLV1srkB7dToTAEqgDSfPtXRJZYH", "Trading Agent", 85, "TRUSTED"),
    ("TTcYhypP8m4phDhN6oRexz2174zAFJ254R", "Payment Bot", 91, "TRUSTED"),
    ("TGzz8gjYiYRqpfmDwnLxfCAEQPhLaBb1gL", "Yield Optimizer", 67, "REPUTABLE"),
    ("THPvaUhoh2Qn2y9THCZML3H4ABSMYu2vLR", "Data Agent", 54, "CAUTION"),
    ("TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9", "Lending Agent", 43, "CAUTION"),
    ("TPYmHEhy5n8TCEfYGqW2rPxsghSfzghPDn", "NFT Agent", 38, "RISKY"),
    ("TKcEU8ekq2ZoFzLSGFYCUY6aocJBX9X31b", "Bridge Bot", 25, "RISKY"),
    ("TAUN6FwrnwwmaEqYcckffC7wYmbaS6cBiX", "Spam Bot", 12, "RISKY"),
    ("TFbXDcD9Yf2G9Q5T2kS3MFCK9VNq1PTP8G", "Scam Agent", 0, "BLACKLISTED"),
]


def main():
    contracts = get_contracts()

    if not contracts.is_ready:
        print("ERROR: Contracts not configured. Check .env")
        sys.exit(1)

    print(f"Seeding {len(AGENTS)} agents on Nile...\n")

    for addr, agent_type, score, verdict in AGENTS:
        print(f"  {agent_type:20s} score={score:3d} ({verdict})")

        # Register (may fail if already registered — that's ok)
        try:
            tx = contracts.register_agent(addr, agent_type)
            if tx:
                print(f"    registered: {tx[:16]}...")
                time.sleep(1)
        except Exception as e:
            if "already registered" in str(e).lower():
                print(f"    already registered")
            else:
                print(f"    register failed: {e}")

        # Update score
        try:
            tx = contracts.update_score(addr, score, verdict)
            if tx:
                print(f"    score set:  {tx[:16]}...")
                time.sleep(1)
        except Exception as e:
            print(f"    score update failed: {e}")

        # Mint passport (may fail if already minted)
        try:
            tx = contracts.mint_passport(addr, agent_type)
            if tx:
                print(f"    passport:   {tx[:16]}...")
                time.sleep(1)
        except Exception as e:
            if "already has" in str(e).lower():
                print(f"    passport already minted")
            else:
                print(f"    passport failed: {e}")

        print()

    print("Done! Check the dashboard at http://localhost:3000/dashboard.html")


if __name__ == "__main__":
    main()
