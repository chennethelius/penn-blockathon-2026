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

# These 6 agents are the Arena demo agents — same addresses used in
# backend/app/routers/arena.py ARENA_AGENTS. Scores chosen for a good demo
# narrative: high → low spread lets judges see approve/block at various thresholds.
ARENA_AGENTS = [
    # (address, agentType, trustScore, verdict)
    # Scores match what's on the Oracle (already seeded)
    ("TLyqzVGLV1srkB7dToTAEqgDSfPtXRJZYH", "Coinbase Pay", 85, "TRUSTED"),
    ("TX5ug3U97zsLdaNTfS5d89WJXTbvthjYPq", "Aave Lend", 72, "REPUTABLE"),
    ("TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9", "Stripe Agent", 43, "CAUTION"),
    ("TAUN6FwrnwwmaEqYcckffC7wYmbaS6cBiX", "Delve", 12, "RISKY"),
]

# Extra agents for the dashboard/passport pages (not shown in Arena)
EXTRA_AGENTS = [
    ("TN3gScUTZC3mejw33P3KyBK72jQomptdy1", "Payment Bot", 91, "TRUSTED"),
    ("TG3CaDhonPJJM1Tuf5N3k5gBYXJBVfbqGS", "Data Agent", 54, "CAUTION"),
    ("TPYmHEhy5n8TCEfYGqW2rPxsghSfzghPDn", "NFT Agent", 38, "RISKY"),
    ("TLND31wtzojkFTJttnid36ZGiLMJ7Gk5S1", "Scam Agent", 0, "BLACKLISTED"),
]

AGENTS = ARENA_AGENTS + EXTRA_AGENTS


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
