<p align="center">
  <img src="https://img.shields.io/badge/PennBlockathon-2026-red?style=for-the-badge" alt="PennBlockathon 2026" />
  <img src="https://img.shields.io/badge/Track-AI%20%26%20Agentic%20Commerce-blue?style=for-the-badge" alt="AI & Agentic Commerce" />
  <img src="https://img.shields.io/badge/Track-Payments%20%26%20DeFi-purple?style=for-the-badge" alt="Payments & DeFi" />
  <img src="https://img.shields.io/badge/Network-Tron%20Nile%20Testnet-green?style=for-the-badge" alt="Tron Nile" />
</p>

<h1 align="center">TronTrust</h1>
<p align="center"><strong>Trust infrastructure for the Tron agent economy.</strong></p>

<p align="center">
  AI agents deploy, transact, and manage trust policies on Tron &mdash; through natural language.<br>
  ML-scored trust gates block risky transfers. x402 micropayments monetize the API.<br>
  Every action is a real on-chain transaction on Nile testnet.
</p>

---

## The Problem

AI agents are transacting autonomously on blockchains. They swap tokens, pay invoices, and interact with smart contracts &mdash; without human oversight. But there's no way for an agent to know if the counterparty is trustworthy.

On Tron, this is especially critical: **over 50% of all USDT circulates on Tron**, making it the largest stablecoin settlement network. Yet there is **zero trust infrastructure** for AI agents on Tron.

## The Solution

TronTrust provides:

- **Trust Scores (0-100)** for any Tron wallet, computed from 50 on-chain features via XGBoost ML
- **Trust-gated Smart Wallet** &mdash; the TrustWallet contract checks the Oracle before sending TRX. Low-score recipients are blocked at the contract level.
- **Soul-bound Passport NFTs** &mdash; non-transferable on-chain identity per agent
- **x402 Paid API** &mdash; agents pay per API call with real on-chain TRX micropayments
- **Account Permission Management** &mdash; locks agent wallets so they can ONLY transact through the TrustWallet (Tron protocol-level enforcement)
- **Natural Language Control** &mdash; deploy agents, send payments, and manage trust policies by typing plain English in the Arena
- **MCP Server** &mdash; 12 tools for Claude and any MCP-compatible AI agent
- **Auto-blacklist** &mdash; 3 community reports set score to 0 across all Guard users

---

## Live Demo: Agent Arena

The Arena is the main demo interface. It uses a Groq-powered LLM (Llama 3.3 70B) to interpret natural language commands and execute real on-chain transactions.

**Try these commands:**

| Command | What happens on-chain |
|---|---|
| `deploy a trading bot called JudgeBot` | Generates Tron keypair, registers on Oracle, mints Passport NFT |
| `send 1 TRX to Coinbase Pay` | Trust check via Oracle + Anubis ML, then TrustWallet sends TRX |
| `send 1 TRX to Delve` | Blocked &mdash; score 12 is below threshold |
| `set min trust to 80` | Updates threshold on TrustWallet contract |
| `check Aave Lend` | Queries Oracle for score, verdict, risk flags |
| `paid lookup on Delve` | x402 flow: 402 response &rarr; real TRX payment &rarr; trust data returned |

Every response includes a clickable TronScan link to the real transaction on Nile testnet.

**Dev toggle:** Click "Dev" to show the agent sidebar, trust gate visualization, and transaction log.

---

## Architecture

```
Natural Language (Arena / MCP / SDK)
              |
              v
  ┌──────────────────────────────────────────┐
  |           FastAPI Gateway (:8000)         |
  |  trust · wallet · arena · passport · x402|
  |  Groq LLM (tool calling)                 |
  └──────────┬──────────────┬────────────────┘
             |              |
  ┌──────────v────┐  ┌──────v───────────────┐
  | Anubis ML     |  | Tron Nile Testnet    |
  | Engine (:8001)|  |                      |
  | XGBoost +     |  | TronTrustOracle      |
  | 50 on-chain   |  | TrustPassport (NFT)  |
  | features      |  | TrustWallet          |
  └───────────────┘  | TrustGateContract    |
                     | CommercialTrust      |
                     | TrustEscrow          |
                     └──────────────────────┘
```

## Deployed Contracts (Nile Testnet)

| Contract | Address | Purpose |
|---|---|---|
| TronTrustOracle | [`TJtw1YMJ...`](https://nile.tronscan.org/#/contract/TJtw1YMJiWujvGns3gFKaQmgEbp36rmnqK) | Trust score storage, agent registration, attestations |
| TrustPassport | [`TNpENknR...`](https://nile.tronscan.org/#/contract/TNpENknRoNcEYbq4R77YgViPK4ZgHHtpqh) | Soul-bound NFT identity per agent |
| TrustWallet | [`TFD31Cr3...`](https://nile.tronscan.org/#/contract/TFD31Cr3PfZPZjPHUWSVstkZ53ZCEyX6yi) | Trust-gated smart account for payments |
| TrustGateContract | [`TT7tFQCG...`](https://nile.tronscan.org/#/contract/TT7tFQCGJLpPYZdsUimMgQWr51pbHzudyv) | DeFi pool access control |
| CommercialTrust | [`TQJrxetk...`](https://nile.tronscan.org/#/contract/TQJrxetkVpzfR7byMTzi1qa4ERdeKvsHYY) | B2B invoice payment reputation |
| TrustEscrow | [`TLnjvkwm...`](https://nile.tronscan.org/#/contract/TLnjvkwmsJkGMx3qTkeUjhvwQhsTH8DGQR) | Trust-tiered escrow (instant to multi-sig) |

---

## Key Features

### Trust-Gated Payments
The TrustWallet contract queries the Oracle before every outgoing transfer. If the recipient's trust score is below the configurable threshold, the transaction reverts at the smart contract level.

### x402 Paid API
Third-party agents pay per API call. The flow follows the HTTP 402 standard:
1. Agent calls `/api/x402/trust` &rarr; gets `402 Payment Required` with price
2. Agent sends TRX payment on-chain
3. Agent retries with payment proof &rarr; receives trust data

In the Arena demo, the payment is a real TRX transfer visible on TronScan.

### Anubis ML Engine
XGBoost risk model trained on real TRC-20 token data. Extracts 50 features from TronGrid and TronScan:
- Behavioral: wallet age, tx frequency, JustLend repayment, SunSwap activity
- Token health: liquidity, holder concentration, honeypot detection, freeze/mint authority
- Threat: mixer interaction, circular payments, phishing association

### Account Permission Management
Uses Tron's native multi-sig system to lock agent wallets at the protocol level. A locked agent can ONLY transact through the TrustWallet contract &mdash; even if the AI is compromised.

### MCP Server (12 Tools)

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
| `deploy_agent` | Generate keypair, register on Oracle, mint Passport NFT |
| `trust_send` | Send TRX with trust gate enforcement |
| `set_min_trust` | Update minimum trust threshold on-chain |
| `check_recipient` | Pre-send trust check with ML risk flags |
| `get_agent_trust` | Full trust score, verdict, breakdown |
| `get_token_forensics` | TRC-20 rug analysis, honeypot detection |
| `lock_agent_permissions` | Lock wallet via Tron Account Permission Management |
| `register_agent` | Register existing address on Oracle |
| `get_agent_reputation` | Community reviews and sentiment |
| `report_outcome` | Report job result, earn Sun Points |
| `get_sun_points_balance` | Points balance and streak |
| `wallet_stats` | Transfer counts, blocks, volume |

### Guard SDK (Python)

```python
from trontrust_guard import TrustGuard

guard = TrustGuard(private_key="...", min_score=60)
result = guard.send_trx("TRecipientAddress", 100)  # Checks trust before sending
```

---

## Scoring Model

| Signal | Weight | Source |
|---|---|---|
| On-chain Behavior | 50% | 25 features from TronGrid: wallet age, tx patterns, energy usage |
| ML Token Health | 30% | 15 features: liquidity, honeypot, freeze/mint, holder concentration |
| Network/Threat | 20% | 10 features: payment graph, mixer interaction, phishing association |

**Verdicts:** TRUSTED (80+) · REPUTABLE (60+) · CAUTION (40+) · RISKY (20+) · BLACKLISTED (<20)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Smart Contracts | Solidity 0.8.6, TronBox, Nile Testnet |
| API Gateway | FastAPI (Python) |
| ML Engine | XGBoost, scikit-learn, NumPy |
| LLM (Arena) | Groq (Llama 3.3 70B) via tool calling |
| Blockchain Data | tronpy, TronGrid, TronScan API |
| MCP Server | Python MCP SDK (12 tools) |
| Frontend | HTML/CSS/JS (vanilla) |
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
# Add your Nile testnet private key, Groq API key, TronGrid key
```

Required `.env` variables:
```
PRIVATE_KEY_NILE=<hex_private_key>
GROQ_API_KEY=<free_from_console.groq.com>
TRONGRID_API_KEY=<from_trongrid.io>
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
- **Passport:** http://localhost:3000/passport.html
- **API Docs:** http://localhost:8000/docs

---

## On-Chain Proof

Every Arena action produces a verifiable Nile testnet transaction:

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
├── backend/          # FastAPI gateway (port 8000)
│   └── app/routers/  # trust, wallet, arena, passport, x402, ...
├── anubis/           # XGBoost ML engine (port 8001)
├── contracts/        # Solidity smart contracts (6 deployed)
├── mcp_server/       # MCP server (12 tools)
├── guard_sdk/        # Python trust-gated wallet SDK
├── scripts/          # Seed agents, utilities
├── arena.html        # Main demo page (Groq-powered chat)
├── dashboard.html    # Trust lookup (Anubis ML)
├── passport.html     # Agent identity viewer
├── index.html        # Landing page
└── styles.css        # Shared design system
```

---

## Team

Built at PennBlockathon 2026.
