# Wrap Slides — Kairos Demo

---

## Slide 1: What We Built

**Kairos — Trust infrastructure for AI agents on Tron**

- 6 smart contracts on Nile testnet
- XGBoost ML engine (50 on-chain features)
- x402 micropayments (real TRX settlement)
- MCP server on npm (`npx kairos-xyz-mcp`)
- Natural language Arena (Groq LLM)
- Python Guard SDK

---

## Slide 2: The Flow

```
Agent deploys  →  Anubis scores  →  Oracle stores  →  TrustWallet enforces  →  x402 monetizes
```

- Every action = verifiable TronScan transaction
- Every payment = trust-gated at the smart contract level
- Every agent = soul-bound Passport NFT

---

## Slide 3: Security

**Tron Account Permission Management**

- Agent wallets locked at the protocol level
- Can ONLY transact through TrustWallet
- Even compromised AI cannot bypass
- Not a smart contract rule — Tron network enforcement

---

## Slide 4: Track Coverage (AI & Agentic Commerce)

| Bounty Direction | Kairos Feature |
|---|---|
| x402 payments on TRON | Real 402 → pay → retry with TRX settlement |
| Discovery + trust beyond ERC-8004 | Oracle + Passport NFT + ML scoring |
| Security via Account Permission Mgmt | Protocol-level agent wallet locking |
| OPSEC dev tooling | Anubis detects wash trading, honeypots, phishing |
| Micro-transaction enablement | Pay-per-call, on-chain receipts |
| Standards alignment | MCP protocol, x402 protocol |

---

## Slide 5: Track Coverage (Payments & DeFi)

| Requirement | Kairos Feature |
|---|---|
| Two roles | Business operator + AI agents |
| Setup / onboarding | Deploy agent via chat or MCP |
| Payment action | Trust-gated TRX send |
| Verifiable outcome | TronScan tx hash for every action |
| Fee/failure UX | Clear blocked/approved messages + reason |
| Innovation | ML-scored trust gates, not basic send/receive |

---

## Slide 6: Business Case

**Kairos is built for businesses running AI payment agents.**

The problem:
- AI agents transact autonomously — no trust verification
- Tron = largest USDT network, #1 target for scams

The solution:
- Deploy an agent → set a trust policy → contracts enforce it
- No wallet setup for end users
- No manual review
- Pay-per-API-call monetization via x402

---

## Slide 7: Links

| | |
|---|---|
| Live site | https://kairosxyz.vercel.app |
| Arena | https://kairosxyz.vercel.app/arena.html |
| Backend API | https://penn-blockathon-2026-production.up.railway.app |
| GitHub | https://github.com/chennethelius/penn-blockathon-2026 |
| npm | https://www.npmjs.com/package/kairos-xyz-mcp |
| Install | `npx -y kairos-xyz-mcp` |
