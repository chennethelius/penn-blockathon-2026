"""
TronTrust Live Demo — 3 Scenarios
==================================
Demonstrates the full trust-gated agent commerce flow against the live API.

Scenario 1: Agent refuses a scam token (token forensics)
Scenario 2: Agent trusts a good counterparty and pays (trust check → payment)
Scenario 3: Community catches a scammer (3 reports → auto-blacklist)

Usage:
  python demo/run_demo.py                         # runs all 3 scenarios
  python demo/run_demo.py --scenario 1            # run specific scenario
  python demo/run_demo.py --api http://localhost:8000  # custom API base

Requires: backend + anubis running (ports 8000 + 8001)
"""

import argparse
import json
import sys
import time
import httpx

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

API_BASE = "http://localhost:8000/api/v1"

# Demo addresses (real Tron mainnet addresses for realistic data)
GOOD_AGENT = "TLyqzVGLV1srkB7dToTAEqgDSfPtXRJZYH"  # known SR address
SCAM_TOKEN = "TScamTokenFakeAddress1234567890abc"       # fake address for demo
BAD_AGENT_1 = "TBadAgent1111111111111111111111111"
BAD_AGENT_2 = "TBadAgent2222222222222222222222222"
BAD_AGENT_3 = "TBadAgent3333333333333333333333333"
SCAM_WALLET = "TScamWallet99999999999999999999999"
REPORTER_1 = "TReporter1111111111111111111111111"
REPORTER_2 = "TReporter2222222222222222222222222"
REPORTER_3 = "TReporter3333333333333333333333333"


def header(text):
    print(f"\n{'='*60}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{'='*60}\n")


def step(num, text):
    print(f"  {BOLD}{YELLOW}[Step {num}]{RESET} {text}")


def result(text, color=GREEN):
    print(f"  {color}→ {text}{RESET}")


def api_get(path):
    r = httpx.get(f"{API_BASE}{path}", timeout=20.0)
    return r.json()


def api_post(path, data):
    r = httpx.post(f"{API_BASE}{path}", json=data, timeout=20.0)
    return r.json()


def scenario_1():
    """Agent refuses a scam token."""
    header("SCENARIO 1: Agent Refuses a Scam Token")

    print(f"  {DIM}An AI agent is asked to swap 500 USDT into an unknown TRC-20 token.{RESET}")
    print(f"  {DIM}Before swapping, the agent checks the token with TronTrust.{RESET}\n")

    step(1, "Agent calls get_token_forensics via MCP...")
    time.sleep(0.5)

    try:
        data = api_get(f"/token/{SCAM_TOKEN}")
        print(f"  {DIM}{json.dumps(data, indent=4)}{RESET}\n")

        rug_prob = data.get("rugProbability", 0.5)
        honeypot = data.get("honeypot", False)
        freeze = data.get("freezeFunction", False)
        verdict = data.get("verdict", "caution")

        step(2, "Agent analyzes the response...")
        time.sleep(0.3)

        if rug_prob > 0.4 or honeypot or freeze or verdict in ("avoid", "caution"):
            result(f"Rug probability: {rug_prob}", RED)
            result(f"Honeypot: {honeypot}", RED if honeypot else GREEN)
            result(f"Freeze function: {freeze}", RED if freeze else GREEN)
            result(f"Verdict: {verdict}", RED)
            print()
            step(3, f"{RED}{BOLD}AGENT REFUSES THE SWAP{RESET}")
            result("Agent saved user from potential loss of 500 USDT", GREEN)
        else:
            result(f"Token appears safe (rug prob: {rug_prob})", GREEN)
            step(3, "Agent would proceed with swap")

    except Exception as e:
        result(f"API call failed: {e}", RED)


def scenario_2():
    """Agent trusts a good counterparty."""
    header("SCENARIO 2: Agent Trusts a Good Counterparty")

    print(f"  {DIM}An AI agent needs to pay another agent 200 USDT for a completed job.{RESET}")
    print(f"  {DIM}Before paying, the agent checks the counterparty's trust score.{RESET}\n")

    step(1, f"Agent calls get_agent_trust for {GOOD_AGENT[:20]}...")
    time.sleep(0.5)

    try:
        data = api_get(f"/agent/{GOOD_AGENT}")
        print(f"  {DIM}{json.dumps(data, indent=4)}{RESET}\n")

        score = data.get("trustScore", 50)
        verdict = data.get("verdict", "caution")
        flags = data.get("flags", [])

        step(2, "Agent evaluates trust...")
        time.sleep(0.3)

        color = GREEN if score >= 60 else YELLOW if score >= 40 else RED
        result(f"Trust score: {score}/100", color)
        result(f"Verdict: {verdict}", color)
        if flags:
            result(f"Flags: {', '.join(flags)}", YELLOW)
        print()

        if score >= 60:
            step(3, f"{GREEN}{BOLD}AGENT PROCEEDS WITH PAYMENT{RESET}")
            result("200 USDT sent to counterparty", GREEN)

            step(4, "Agent reports successful outcome → earns 5 Sun Points")
            outcome = api_post("/outcome", {
                "queryId": f"demo-{int(time.time())}",
                "outcome": "success",
                "reporter": GOOD_AGENT,
            })
            result(f"Outcome reported. Sun Points earned: {outcome.get('sunPointsEarned', 5)}", GREEN)
        else:
            step(3, f"{YELLOW}AGENT HOLDS — requesting escrow{RESET}")
            result(f"Score too low ({score}). Agent requests escrow protection.", YELLOW)

    except Exception as e:
        result(f"API call failed: {e}", RED)


def scenario_3():
    """Community catches a scammer via collective immunity."""
    header("SCENARIO 3: Community Catches a Scammer")

    print(f"  {DIM}Three independent agents report the same malicious address.{RESET}")
    print(f"  {DIM}After 3 reports, TronTrust auto-blacklists and all Guard users block instantly.{RESET}\n")

    reporters = [
        (REPORTER_1, "energy_drain"),
        (REPORTER_2, "fake_usdt"),
        (REPORTER_3, "address_poisoning"),
    ]

    for i, (reporter, threat_type) in enumerate(reporters, 1):
        step(i, f"Reporter {i} files threat report ({threat_type})...")
        time.sleep(0.4)

        try:
            data = api_post("/threat/report", {
                "maliciousAddress": SCAM_WALLET,
                "threatType": threat_type,
                "evidence": f"Demo evidence from reporter {i}",
                "reporterAddress": reporter,
            })
            print(f"  {DIM}{json.dumps(data, indent=4)}{RESET}\n")

            report_count = data.get("reportCount", i)
            blacklisted = data.get("autoBlacklisted", False)

            result(f"Report #{report_count} filed. Sun Points: +{data.get('sunPointsEarned', 5)}", GREEN)

            if blacklisted:
                print()
                result(f"{RED}{BOLD}AUTO-BLACKLISTED!{RESET}", RED)
                result("Oracle.blacklist() called on-chain → score set to 0", RED)
                result("All TronTrust Guard users now block this address", RED)

        except Exception as e:
            result(f"API call failed: {e}", RED)

    print()
    step(4, "Verifying blacklist — checking trust score...")
    time.sleep(0.3)
    try:
        data = api_get(f"/agent/{SCAM_WALLET}")
        score = data.get("trustScore", "?")
        verdict = data.get("verdict", "?")
        result(f"Score: {score}, Verdict: {verdict}", RED)
    except Exception as e:
        result(f"Verification failed: {e}", RED)


def main():
    global API_BASE
    parser = argparse.ArgumentParser(description="TronTrust Live Demo")
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3], help="Run specific scenario")
    parser.add_argument("--api", default=API_BASE, help="API base URL")
    args = parser.parse_args()
    API_BASE = args.api

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║         TronTrust — Live Demo                    ║{RESET}")
    print(f"{BOLD}{CYAN}║   Trust Layer for the Tron Agent Economy          ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════╝{RESET}")
    print(f"\n  {DIM}API: {API_BASE}{RESET}")

    # Health check
    try:
        health = httpx.get(f"{API_BASE.replace('/api/v1','')}/health", timeout=5).json()
        result(f"Backend: {health.get('status', '?')}", GREEN)
    except Exception:
        result("Backend unreachable! Start with: uvicorn app.main:app --port 8000", RED)
        sys.exit(1)

    scenarios = {1: scenario_1, 2: scenario_2, 3: scenario_3}

    if args.scenario:
        scenarios[args.scenario]()
    else:
        for s in [1, 2, 3]:
            scenarios[s]()
            if s < 3:
                print(f"\n  {DIM}{'─'*50}{RESET}")

    print(f"\n{BOLD}{GREEN}  Demo complete.{RESET}\n")


if __name__ == "__main__":
    main()
