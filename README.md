<p align="center">
  <img src="https://img.shields.io/badge/PennBlockathon-2026-red?style=for-the-badge" alt="PennBlockathon 2026" />
  <img src="https://img.shields.io/badge/Track-AI%20%26%20Agentic%20Commerce-blue?style=for-the-badge" alt="AI & Agentic Commerce" />
  <img src="https://img.shields.io/badge/Track-Payments%20%26%20DeFi-purple?style=for-the-badge" alt="Payments & DeFi" />
  <img src="https://img.shields.io/badge/Network-Tron%20Nile%20Testnet-green?style=for-the-badge" alt="Tron Nile" />
</p>

<h1 align="center">Kairos</h1>
<p align="center"><strong>Trust infrastructure for the Tron agent economy.</strong></p>

<p align="center">
  AI agents deploy, transact, and manage trust policies on Tron &mdash; through natural language.<br>
  ML-scored trust gates block risky transfers. x402 micropayments monetize the API.<br>
  Every action is a real on-chain transaction on Nile testnet.
</p>

<p align="center">
  <a href="https://kairosxyz.vercel.app"><strong>Live Site</strong></a> &middot;
  <a href="https://kairosxyz.vercel.app/arena.html"><strong>Arena</strong></a> &middot;
  <a href="https://www.npmjs.com/package/kairos-xyz-mcp"><strong>npm</strong></a> &middot;
  <a href="https://penn-blockathon-2026-production.up.railway.app/docs"><strong>API Docs</strong></a>
</p>

---

## Install

```bash
npx kairos-xyz-mcp
```

Or add to your Claude / Cursor / MCP config:

```json
{
  "mcpServers": {
    "kairos": {
      "command": "npx",
      "args": ["-y", "kairos-xyz-mcp"]
    }
  }
}
```

8 tools. No Python, no API keys, no setup.

---

## The Problem

AI agents are transacting autonomously on blockchains &mdash; swapping tokens, paying invoices, interacting with contracts &mdash; without human oversight. There's no way for an agent to know if the counterparty is trustworthy.

On Tron, this is critical: **$7.9T in annual USDT volume**, the largest stablecoin settlement network. Yet there is **zero trust infrastructure** for AI agents.

## The Solution

Kairos provides:

- **Trust Scores (0-100)** for any Tron wallet, computed from 50 on-chain features via XGBoost ML
- **Trust-gated Smart Wallet** &mdash; the TrustWallet contract reads the Oracle and sends in the same transaction. Score too low, the EVM reverts. Money never moves.
- **Soul-bound Passport NFTs** &mdash; non-transferable identity. Transfer functions revert. SVG renders from on-chain state &mdash; no IPFS.
- **x402 Paid API** &mdash; 402 Payment Required &rarr; TRX payment on-chain &rarr; trust data returned. Real micropayments.
- **Account Permission Management** &mdash; rewrites agent wallet permissions at the Tron protocol level. Locked agents can ONLY transact through the TrustWallet. Even a compromised AI cannot bypass it &mdash; the network rejects it.
- **Natural Language Arena** &mdash; deploy agents, send payments, manage policies in plain English via Groq LLM (Llama 3.3 70B)
- **MCP Server on npm** &mdash; 8 tools, any MCP-compatible AI agent connects in one line
- **Python Guard SDK** &mdash; trust-gated wallet wrapper in 3 lines of code

---

## Live Demo: Agent Arena

The Arena at [kairosxyz.vercel.app/arena.html](https://kairosxyz.vercel.app/arena.html) interprets natural language commands and executes real on-chain transactions.

| Command | What happens |
|---|---|
| `deploy a trading bot called JudgeBot` | Generates Tron keypair, registers on Oracle, mints Passport NFT |
| `send 1 TRX to Coinbase Pay` | Trust check via Oracle + Anubis ML &rarr; TrustWallet sends TRX |
| `send 1 TRX to Delve` | Blocked &mdash; score 12 below threshold, contract reverts |
| `set min trust to 80` | Updates threshold on TrustWallet contract |
| `paid lookup on Coinbase Pay` | x402: 402 response &rarr; real TRX payment &rarr; trust data |

Every response includes a clickable TronScan link. **Dev toggle** shows the agent sidebar, trust gate visualization, and transaction log.

Deployed agents persist across sessions. Pre-seeded agents: Coinbase Pay (85), Aave Lend (72), Stripe Agent (43), Delve (12).

---

## Architecture

```
Arena (Groq LLM)    MCP (npm)    Guard SDK    x402 API
       \               |            |           /
        v              v            v          v
  ┌──────────────────────────────────────────────┐
  |            FastAPI Gateway (:8000)            |
  |   arena · trust · wallet · passport · x402   |
  |   Groq tool calling · rate limiting           |
  └──────────┬──────────────────┬────────────────┘
             |                  |
  ┌──────────v──────┐   ┌──────v───────────────┐
  | Anubis ML       |   | Tron Nile Testnet    |
  | Engine (:8001)  |   |                      |
  | XGBoost + 50    |   | TronTrustOracle      |
  | on-chain        |   | TrustPassport (NFT)  |
  | features        |   | TrustWallet          |
  └─────────────────┘   | TrustGateContract    |
                         | CommercialTrust      |
                         | TrustEscrow          |
                         └──────────────────────┘
```

### How It Works

1. **Agent deploys** &rarr; backend generates Tron keypair, calls `Oracle.registerAgent`, mints Passport NFT
2. **Anubis scores** &rarr; extracts 50 features from TronGrid/TronScan, XGBoost predicts risk
3. **Oracle stores** &rarr; score written on-chain, readable by any contract
4. **TrustWallet enforces** &rarr; reads Oracle during `send()`, reverts if score < threshold
5. **x402 monetizes** &rarr; 402 response with price, agent pays TRX, retries with receipt

---

## Deployed Contracts (Nile Testnet)

| Contract | Address | Purpose |
|---|---|---|
| TronTrustOracle | [`TJtw1YMJ...`](https://nile.tronscan.org/#/contract/TJtw1YMJiWujvGns3gFKaQmgEbp36rmnqK) | Trust score storage, agent registration, attestations |
| TrustPassport | [`TNpENknR...`](https://nile.tronscan.org/#/contract/TNpENknRoNcEYbq4R77YgViPK4ZgHHtpqh) | Soul-bound TRC-721, on-chain SVG, non-transferable |
| TrustWallet | [`TFD31Cr3...`](https://nile.tronscan.org/#/contract/TFD31Cr3PfZPZjPHUWSVstkZ53ZCEyX6yi) | Trust-gated smart account, internal Oracle reads |
| TrustGateContract | [`TT7tFQCG...`](https://nile.tronscan.org/#/contract/TT7tFQCGJLpPYZdsUimMgQWr51pbHzudyv) | DeFi pool access control |
| CommercialTrust | [`TQJrxetk...`](https://nile.tronscan.org/#/contract/TQJrxetkVpzfR7byMTzi1qa4ERdeKvsHYY) | B2B invoice reputation, recommended payment terms |
| TrustEscrow | [`TLnjvkwm...`](https://nile.tronscan.org/#/contract/TLnjvkwmsJkGMx3qTkeUjhvwQhsTH8DGQR) | Trust-tiered escrow (instant release to multi-sig) |

---

## Key Features

### Trust-Gated Payments
The TrustWallet reads the Oracle and sends in the same transaction. If the score is below the threshold, the whole thing reverts &mdash; the money never moves. Enforcement happens inside the contract execution, not in the backend.

### x402 Paid API
Follows the HTTP 402 standard with real on-chain settlement:
1. Agent calls `/api/x402/trust` &rarr; gets `402 Payment Required` with price
2. Agent sends TRX on-chain to treasury
3. Agent retries with payment proof &rarr; receives trust data

### Anubis ML Engine
XGBoost risk model trained on real TRC-20 token data. 50 features:
- **Behavioral** (25): wallet age, tx patterns, JustLend repayment, SunSwap activity, energy usage
- **Token Health** (15): liquidity, holder concentration, honeypot detection, freeze/mint authority
- **Threat** (10): payment graph centrality, mixer interaction, circular payments, phishing clusters

**Verdicts:** TRUSTED (80+) &middot; REPUTABLE (60+) &middot; CAUTION (40+) &middot; RISKY (20+) &middot; BLACKLISTED (<20)

### Account Permission Management
Uses Tron's native multi-sig to constrain AI agents. We rewrite the agent's active permission so the only contract it can interact with is the TrustWallet. If the key leaks &mdash; if the AI goes rogue &mdash; the Tron node rejects any transaction not routed through our contract. Protocol-level enforcement.

### MCP Server (8 Tools, npm)

```bash
npx kairos-xyz-mcp
```

| Tool | Description |
|---|---|
| `deploy_agent` | Generate keypair, register on Oracle, mint Passport NFT |
| `trust_send` | Send TRX with trust gate enforcement |
| `set_min_trust` | Update minimum trust threshold on-chain |
| `check_recipient` | Pre-send trust check with ML risk flags |
| `get_agent_trust` | Full trust score, verdict, breakdown |
| `get_token_forensics` | TRC-20 rug analysis, honeypot detection |
| `wallet_stats` | Transfer counts, blocks, volume |
| `lock_agent_permissions` | Lock wallet via Account Permission Management |

### Guard SDK (Python)

```python
from trontrust_guard import TrustGuard

guard = TrustGuard(private_key="...", min_score=60)
result = guard.send_trx("TRecipientAddress", 100)  # Checks trust before sending
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Smart Contracts | Solidity 0.8.6, TronBox, Nile Testnet |
| API Gateway | FastAPI (Python), 10 routers |
| ML Engine | XGBoost, scikit-learn, NumPy |
| LLM (Arena) | Groq (Llama 3.3 70B) via tool calling |
| Blockchain Data | tronpy, TronGrid REST, TronScan API |
| MCP Server | Node.js, published on npm |
| Frontend | HTML/CSS/JS (vanilla), Vercel |
| Backend Hosting | Railway |
| Guard SDK | Python (tronpy wrapper) |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/chennethelius/penn-blockathon-2026.git
cd penn-blockathon-2026
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r anubis/requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Required variables:
```
PRIVATE_KEY_NILE=<hex_private_key>
GROQ_API_KEY=<free_from_console.groq.com>
TRONGRID_API_KEY=<from_trongrid.io>
TRONSCAN_API_KEY=<from_tronscan.org>
TRON_NETWORK=nile
```

### 3. Seed agents (first time only)

```bash
cd backend && python ../scripts/seed_agents.py
```

### 4. Run

```bash
# Terminal 1: Anubis ML Engine
cd anubis && uvicorn main:app --port 8001

# Terminal 2: API Gateway
cd backend && uvicorn app.main:app --port 8000 --reload

# Terminal 3: Frontend
python3 -m http.server 3000
```

### 5. Open

- **Arena:** http://localhost:3000/arena.html
- **Lookup:** http://localhost:3000/dashboard.html
- **MCP:** http://localhost:3000/mcp.html
- **API Docs:** http://localhost:8000/docs

---

## On-Chain Proof

Every action produces a verifiable Nile testnet transaction:

- **Agent deployment:** Oracle `registerAgent` tx + Passport `mint` tx
- **Trust-gated send:** TrustWallet `send` tx (or revert if score < threshold)
- **Threshold update:** TrustWallet `setMinTrustScore` tx
- **x402 payment:** TRX transfer from TrustWallet to treasury
- **Permission lock:** Tron `AccountPermissionUpdate` tx

All tx hashes link to [Nile TronScan](https://nile.tronscan.org).

---

## Project Structure

```
penn-blockathon-2026/
├── backend/           # FastAPI gateway (port 8000)
│   └── app/routers/   # arena, trust, wallet, passport, x402, ...
├── anubis/            # XGBoost ML engine (port 8001)
├── contracts/         # Solidity smart contracts (6 deployed)
├── kairos-mcp/        # npm MCP server package
├── mcp_server/        # Python MCP server (12 tools)
├── guard_sdk/         # Python trust-gated wallet SDK
├── scripts/           # Seed agents, utilities
├── slides/            # Architecture + demo slides (SVG)
├── arena.html         # Main demo — Groq-powered chat
├── dashboard.html     # Trust lookup — Anubis ML
├── mcp.html           # MCP install + tools + Passport
├── index.html         # Landing page
└── styles.css         # Shared design system
```

---

## Links

| | |
|---|---|
| Live Site | https://kairosxyz.vercel.app |
| Arena | https://kairosxyz.vercel.app/arena.html |
| Backend API | https://penn-blockathon-2026-production.up.railway.app |
| API Docs | https://penn-blockathon-2026-production.up.railway.app/docs |
| npm | https://www.npmjs.com/package/kairos-xyz-mcp |
| GitHub | https://github.com/chennethelius/penn-blockathon-2026 |

---

## Team

Built at PennBlockathon 2026.
