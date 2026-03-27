<p align="center">
  <img src="https://img.shields.io/badge/PennBlockathon-2026-red?style=for-the-badge" alt="PennBlockathon 2026" />
  <img src="https://img.shields.io/badge/Track-AI%20%26%20Agentic%20Commerce-blue?style=for-the-badge" alt="AI & Agentic Commerce" />
  <img src="https://img.shields.io/badge/Network-Tron%20Nile%20Testnet-green?style=for-the-badge" alt="Tron Nile" />
</p>

<h1 align="center">TronTrust</h1>
<p align="center"><strong>The trust layer for the Tron agent economy.</strong></p>

<p align="center">
  TronTrust scores every wallet on Tron &mdash; AI agents, smart contracts, and businesses &mdash;<br>
  using on-chain behavior, ML risk analysis, and community reputation.<br>
  Agents connect via MCP. Contracts enforce trust on-chain. Scammers get auto-blacklisted.
</p>

---

## The Problem

AI agents are transacting autonomously on blockchains. They swap tokens, pay invoices, and interact with smart contracts &mdash; without human oversight. But there's no way for an agent to know if the counterparty is trustworthy.

On Tron, this is especially critical: **over 50% of all USDT circulates on Tron**, making it the largest stablecoin settlement network. Yet there is **zero trust infrastructure** for AI agents on Tron. No reputation system, no agent identity, no scam prevention layer.

## The Solution

TronTrust provides:

- **Trust Scores (0-100)** for any Tron wallet, computed from 50 on-chain features via XGBoost ML
- **Soul-bound Passport NFTs** &mdash; non-transferable on-chain identity per agent
- **Trust-gated Escrow** &mdash; release conditions adapt to buyer trust score
- **Sentinel Threat Detection** &mdash; energy drain, fake USDT, freeze abuse, address poisoning
- **MCP Server** &mdash; any AI agent connects with one config line
- **Auto-blacklist** &mdash; 3 community reports set score to 0 across all Guard users

---

## Architecture

```
AI Agents (MCP)     Developers (API)     Humans (Frontend)
       \                  |                  /
        v                 v                 v
    ┌──────────────────────────────────────────┐
    |           FastAPI Gateway (:8000)         |
    |   trust · token · sentinel · passport    |
    |   commercial · sunpoints · x402          |
    └──────────┬──────────────┬────────────────┘
               |              |
    ┌──────────v────┐  ┌──────v───────────────┐
    | Anubis ML     |  | Tron Nile Testnet    |
    | Engine (:8001)|  |                      |
    | XGBoost +     |  | TronTrustOracle      |
    | Monte Carlo + |  | TrustPassport (NFT)  |
    | Sentinel      |  | TrustGateContract    |
    └───────────────┘  | CommercialTrust      |
                       | TrustEscrow          |
                       └──────────────────────┘
```

## Deployed Contracts (Nile Testnet)

| Contract | Address | TronScan |
|---|---|---|
| TronTrustOracle | `TJtw1YMJiWujvGns3gFKaQmgEbp36rmnqK` | [View](https://nile.tronscan.org/#/contract/TJtw1YMJiWujvGns3gFKaQmgEbp36rmnqK) |
| TrustPassport | `TNpENknRoNcEYbq4R77YgViPK4ZgHHtpqh` | [View](https://nile.tronscan.org/#/contract/TNpENknRoNcEYbq4R77YgViPK4ZgHHtpqh) |
| TrustGateContract | `TT7tFQCGJLpPYZdsUimMgQWr51pbHzudyv` | [View](https://nile.tronscan.org/#/contract/TT7tFQCGJLpPYZdsUimMgQWr51pbHzudyv) |
| CommercialTrust | `TQJrxetkVpzfR7byMTzi1qa4ERdeKvsHYY` | [View](https://nile.tronscan.org/#/contract/TQJrxetkVpzfR7byMTzi1qa4ERdeKvsHYY) |
| TrustEscrow | `TLnjvkwmsJkGMx3qTkeUjhvwQhsTH8DGQR` | [View](https://nile.tronscan.org/#/contract/TLnjvkwmsJkGMx3qTkeUjhvwQhsTH8DGQR) |

---

## How It Works

### 1. Agent Checks Trust Before Transacting

```
Agent: "Should I send 500 USDT to TWallet789?"
  → MCP tool: get_agent_trust("TWallet789")
  → Anubis extracts 50 features from TronGrid/TronScan
  → XGBoost predicts rug probability: 0.03
  → Score: 87 / TRUSTED
  → Agent proceeds with payment
```

### 2. Agent Refuses a Scam Token

```
Agent: "Should I swap into TRC-20 token TXyz?"
  → MCP tool: get_token_forensics("TXyz")
  → Anubis detects: freeze_function=true, honeypot=0.91
  → Verdict: AVOID — rug probability 0.91
  → Agent refuses the swap, saves the user's funds
```

### 3. Community Auto-Blacklists a Scammer

```
Reporter 1: report_threat("TScamAddr", "energy_drain")  → 1/3
Reporter 2: report_threat("TScamAddr", "fake_usdt")     → 2/3
Reporter 3: report_threat("TScamAddr", "address_poison") → 3/3
  → Oracle.blacklist() called on-chain → score = 0
  → All Guard users instantly block TScamAddr
```

---

## Scoring Model

| Signal | Weight | Source |
|---|---|---|
| **On-chain Behavior** | 50% | 25 features from TronGrid: wallet age, tx patterns, JustLend repayment, SunSwap activity, energy usage |
| **ML Token Health** | 30% | 15 features: liquidity, holder concentration, honeypot, freeze/mint authority, audit status |
| **Network/Threat** | 20% | 10 features: payment graph centrality, mixer interaction, phishing association, address poisoning |

**Verdicts:** TRUSTED (80+) · REPUTABLE (60+) · CAUTION (40+) · RISKY (20+) · BLACKLISTED (<20)

---

## Smart Contracts

### TronTrustOracle
On-chain trust score storage. Any smart contract on Tron can call `getTrust(address)` to check trustworthiness. Operator updates scores from Anubis ML results.

### TrustPassport (TRC-721, Soul-bound)
One non-transferable NFT per wallet. `transferFrom()` reverts. On-chain SVG shows score badge that updates in real time. Stores trust score, commercial score, agent type, Sun Points.

### TrustGateContract
DeFi pool gating. Pool deployers set a minimum trust score. `checkAccess(agent)` queries the Oracle and grants/denies access. Works with any DEX on Tron.

### CommercialTrust
B2B payment reputation. Records invoice settlements, computes relationship scores, and returns recommended terms (net-30 for score 80+, escrow for score <40).

### TrustEscrow
Trust-gated escrow with 4 release tiers:
- Score >= 80: instant release
- Score >= 60: 24h time lock
- Score >= 40: seller confirmation required
- Score < 40: seller + arbiter approval needed

Supports TRX and TRC-20 (USDT) deposits. 0.5% protocol fee.

---

## MCP Server (6 Tools)

Any AI agent connects with one config:

```json
{
  "mcpServers": {
    "trontrust": {
      "command": "python",
      "args": ["mcp_server/server.py"]
    }
  }
}
```

| Tool | Description |
|---|---|
| `get_agent_trust` | Trust score, verdict, risk flags, breakdown |
| `get_token_forensics` | TRC-20 rug analysis, honeypot, freeze/mint detection |
| `get_agent_reputation` | Community reviews, sentiment, avg rating |
| `report_outcome` | Report job result, earn 5 Sun Points |
| `get_sun_points_balance` | Points balance, streak, total earned |
| `register_agent` | Register on-chain, mint Passport NFT |

---

## Anubis ML Engine

XGBoost binary classifier trained on 50,000 synthetic Tron wallets with 50 features.

**5 scam profiles detected:** rug pulls, wash trading, honeypot tokens, energy drain attacks, phishing operations.

**Monte Carlo simulation:** 10,000 perturbations per query with calibrated noise per feature. Returns p5/p25/p50/p75/p95 confidence bands.

**Sentinel:** Background monitor polling TronGrid every 30s for energy drain, fake USDT contracts, freeze abuse, and permission bypass attempts.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Smart Contracts | Solidity 0.8.6, TronBox, Nile Testnet |
| API Gateway | FastAPI (Python) |
| ML Engine | XGBoost, scikit-learn, NumPy |
| Blockchain Data | tronpy, TronGrid REST, TronScan API |
| MCP Server | Python MCP SDK |
| Frontend | HTML/CSS/JS (vanilla) |
| Wallet | TronLink |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/chennethelius/penn-blockathon-2026.git
cd penn-blockathon-2026
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r anubis/requirements.txt
brew install libomp  # macOS only, for XGBoost
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Nile testnet private key
```

### 3. Run

```bash
# Terminal 1: Anubis ML Engine
cd anubis && uvicorn main:app --port 8001

# Terminal 2: API Gateway
cd backend && uvicorn app.main:app --port 8000

# Terminal 3: Frontend
python3 -m http.server 3000
```

### 4. Open

- Frontend: http://localhost:3000/index.html
- Dashboard: http://localhost:3000/dashboard.html
- API Docs: http://localhost:8000/docs
- Anubis Docs: http://localhost:8001/docs

### 5. Demo

```bash
python demo/run_demo.py  # Runs 3 scenarios against live API
```

---

## What Makes TronTrust Different

**vs. Maiat (Base):** TronTrust indexes the entire Tron ecosystem (TronGrid, JustLend, SunSwap, USDT-TRC20 graph) vs. Maiat's ACP-only data. Adds B2B commercial trust, trust-gated escrow, and Tron-specific threat detection.

**vs. Solana reputation projects:** Not just a score &mdash; trust has utility. TrustGate blocks untrusted wallets from DeFi. Escrow adapts to trust. CommercialTrust auto-computes credit terms. Sentinel auto-blacklists.

**First on Tron:** No trust/reputation infrastructure exists on Tron today. TronTrust is the first.

---

## Team

Built at PennBlockathon 2026.

---

## Note

Demo video will be created using [Remotion](https://remotion.dev/).
