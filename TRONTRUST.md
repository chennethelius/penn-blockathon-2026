# AI & Agentic Commerce

–
Build TronTrust — the trust layer for the Tron agent economy.
Reference implementation: https://maiat.io (live on Base).
Read their full docs at https://app.maiat.io/docs and https://app.maiat.io/skill.md before writing any code.


We are rebuilding Maiat on Tron with meaningful improvements. Here is exactly what Maiat does and where we improve on it:


## What Maiat Does (copy this architecture exactly, then improve)
- Trust scores (0-100) for any agent wallet
- Score = 50% on-chain behavioral + 30% ML token health (XGBoost, 50 features) + 20% community reviews
- Wadjet: ML risk engine with rug prediction, Monte Carlo simulation, Sentinel real-time alerts
- TrustGateHook: Uniswap v4 hook blocking untrusted agents from pools
- MCP server: 5 tools (get_agent_trust, get_token_forensics, get_agent_reputation, report_outcome, get_scarab_balance)
- Maiat Guard: wallet wrapper SDK that auto-checks trust before every tx
- Agent Passport: soul-bound NFT identity per wallet (ERC-8004)
- x402 paid API endpoints (pay-per-call via USDC)
- Community reviews + Scarab points incentive system
- Sentinel: real-time monitoring, auto-blacklist after 3 reports
- EAS attestations on-chain


## Where TronTrust Improves On Maiat


### 1. Richer Behavioral Data (Tron-specific, vs. Virtuals ACP only)
Maiat only indexes Virtuals Protocol ACP job history.
TronTrust indexes the entire Tron ecosystem:
- TronGrid/TronScan: full tx history, contract interactions, energy usage patterns
- JustLend: lending repayment rate, borrow/repay ratio (strongest trust signal on Tron)
- SunSwap: trading behavior, wash trading detection, LP manipulation scoring
- USDT-TRC20 transfer graph: payment reliability, counterparty diversity, velocity
- Smart contract deployment history: audited vs unaudited
- Energy drain pattern detection (Tron-specific attack vector)
- USDT phishing contract association scoring
This gives TronTrust 50 Tron-native features vs. Maiat's ACP-only behavioral data.


### 2. Commercial Trust Layer (B2B — not in Maiat at all)
Maiat is purely agent-to-agent trust.
TronTrust adds B2B commercial trust:
- PayClaw invoice settlement history directly feeds trust scores
  (after every paid invoice, POST /trust/record-payment updates both wallets)
- Wallets get a "commercial trust subscore" alongside agent trust
- TermsEngine: trust scores automatically compute payment terms
  (score > 80 → net-30 auto-approved, score < 40 → escrow required)
- TrustPassport shows both agent score AND commercial score side by side
This makes TronTrust useful for businesses, not just AI agent developers.


### 3. Tron-Specific Sentinel Threat Types
Maiat Sentinel watches for generic rug signals.
TronTrust Sentinel adds Tron-specific threat detection:
- Energy drain attacks (malicious contracts draining victim energy)
- Fake USDT contracts (TRC-20 contracts spoofing USDT address)
- Freeze authority abuse (hidden freeze functions in TRC-20 tokens)
- Permission system bypass attempts (Tron multi-sig abuse)
- Super Representative vote manipulation
- Address poisoning with Tron vanity addresses


### 4. SunSwap TrustGate (vs. Uniswap v4 Hook)
Maiat has TrustGateHook for Uniswap v4 on Base.
TronTrust deploys TrustGateContract that SunSwap pool deployers
can reference to gate pool access by minimum trust score.


### 5. Sun Points (vs. Scarab)
Same feedback incentive mechanic as Maiat's Scarab points,
renamed Sun Points to fit Tron's SUN token ecosystem.
Earn 5 Sun Points per outcome report, 10 per verified review.


### 6. Anubis ML Engine (vs. Wadjet)
Same XGBoost architecture as Wadjet, but trained on Tron data:
- 50 Tron-native features (see below)
- Monte Carlo simulation for confidence intervals
- Sentinel real-time monitoring
- Rug prediction specialized for TRC-20 tokens and Tron contracts


---


## Tech Stack
- Frontend: Next.js 14 + TailwindCSS + shadcn/ui
- API Gateway: FastAPI (Python)
- ML Engine (Anubis): Python — XGBoost, scikit-learn, separate service
- Blockchain reads: tronpy (Python), TronGrid REST API
- Blockchain writes: TronWeb.js (for wallet interactions in frontend)
- Database: PostgreSQL via Supabase
- Cache/Rate limiting: Redis via Upstash
- Smart contracts: Solidity TVM-compatible, Nile testnet
- MCP Server: Python mcp SDK
- AI scoring: Anthropic Claude API (review quality scoring)
- Auth: TronLink wallet connect (no Privy — Tron doesn't use EVM auth)


---


## Smart Contracts (TVM-compatible Solidity, deploy to Nile testnet)


### 1. TronTrustOracle.sol
On-chain oracle any smart contract can query for trust scores.
- Owner/operator separation: cold wallet owner, hot wallet operator
- updateScore(address, uint8 score, uint8 verdict) — operator only
- batchUpdateScores(address[], uint8[], uint8[]) — operator only
- registerAgent(address, string agentType) — operator only
- blacklist(address, string reason) — operator only, sets score to 0
- getTrust(address) returns (score, verdict, isTrusted bool)
- isTrusted(address, uint8 minScore) returns bool
- createAttestation(address subject, uint8 score, string evidenceCid) returns bytes32
- AgentProfile struct: agentType, registeredAt, totalJobs, completedJobs, totalVolumeUsdt
- TrustScore struct: score, verdict, lastUpdated
- Events: ScoreUpdated, AgentRegistered, Blacklisted, AttestationCreated


### 2. TrustPassport.sol (TRC-721 soul-bound)
- One NFT per wallet, non-transferable (override transfer to revert)
- Stores: trustScore, agentType, registeredAt, sunPoints, commercialScore
- mint(address, string agentType) — operator only
- updateScore(address, uint8 score, uint8 commercialScore) — operator only
- addSunPoints(address, uint32 points) — operator only
- tokenURI returns on-chain generated SVG showing score badge + verdict color
- getPassport(address) returns full struct


### 3. TrustGateContract.sol
SunSwap pool trust gating.
- References TronTrustOracle
- checkAccess(address agent) returns bool — used by pool deployers
- setMinScore(uint8) — pool owner only
- exempt(address, bool) — whitelist specific agents
- Events: AccessGranted(agent, score), AccessDenied(agent, score)


### 4. CommercialTrust.sol (TronTrust exclusive)
B2B payment relationship registry. Called by PayClaw after settlements.
- CommercialRelationship struct: partyA, partyB, invoicesTotal, invoicesPaid,
  invoicesOverdue, avgPaymentDays, totalVolumeUsdt, relationshipScore
- recordInvoicePayment(payer, payee, amountUsdt, daysToPayment, wasOverdue)
  — authorized callers only (PayClaw contract address)
- getCommercialScore(address a, address b) returns uint8
- getRecommendedTerms(buyer, merchant) returns (paymentWindowDays, requiresEscrow, creditLimitUsdt)
- Relationship key: keccak256(sorted(partyA, partyB))


---


## Anubis ML Engine


Separate FastAPI service. This is the Wadjet equivalent.


### Feature Set (50 Tron-native features)


BEHAVIORAL (25):
1. tx_count_total
2. tx_count_30d
3. tx_count_7d
4. unique_counterparties_total
5. unique_counterparties_30d
6. avg_tx_value_usdt
7. max_tx_value_usdt
8. usdt_tx_ratio (usdt txs / total txs)
9. contract_interaction_ratio
10. smart_contract_deployments
11. wallet_age_days
12. days_since_last_tx
13. trx_balance_current
14. usdt_balance_current
15. energy_usage_pattern (0=irregular, 1=regular)
16. bandwidth_efficiency_ratio
17. trc20_token_diversity
18. justlend_repayment_rate (most important feature)
19. justlend_total_borrowed_usdt
20. justlend_total_repaid_usdt
21. sunswap_trade_frequency
22. sunswap_wash_trading_score (self-trade ratio — higher = worse)
23. lp_manipulation_score
24. commercial_payment_on_time_rate (from CommercialTrust)
25. invoice_completion_rate (from PayClaw)


TOKEN HEALTH (15):
26. token_liquidity_usd
27. token_holder_count
28. top10_holder_concentration
29. token_age_days
30. price_volatility_7d
31. volume_to_liquidity_ratio
32. honeypot_probability
33. freeze_function_present (bool)
34. mint_function_present (bool)
35. owner_renounced (bool)
36. audit_score (0=none, 1=community, 2=professional)
37. dex_listings_count
38. transfer_tax_rate
39. max_transaction_limit_present (bool)
40. blacklist_function_present (bool)


NETWORK/THREAT (10):
41. payment_graph_centrality
42. counterparty_avg_trust_score
43. incoming_tx_diversity_score
44. outgoing_tx_diversity_score
45. circular_payment_ratio
46. energy_drain_victim_count (attacks launched)
47. phishing_contract_association_score
48. mixer_interaction_score
49. address_poisoning_attempts
50. permission_bypass_attempts


### Anubis Endpoints
POST /predict/agent — returns rug probability for agent wallet
POST /predict/token — returns rug probability for TRC-20 token
GET /anubis/{address} — full risk profile + Monte Carlo simulation
  Monte Carlo: 10K simulations with feature perturbation → p5/p25/p75/p95 confidence bands
GET /sentinel/alerts — real-time monitoring alerts
  Alert types: energy_drain, fake_usdt, freeze_abuse, permission_bypass, sr_manipulation
GET /risks/summary — dashboard summary of current threat landscape
GET /health — service health


### Model Training
For demo: train XGBoost on synthetic data with realistic Tron patterns.
Labels: trustworthy (wallet_age > 90d, repayment_rate > 0.8, no honeypot signals)
        risky (new wallet, wash trading detected, honeypot signals, freeze function)
n_estimators=200, max_depth=6, learning_rate=0.1
Save to models/anubis_v1.json
Feature importance: justlend_repayment_rate and wallet_age_days should rank highest.


---


## API Gateway (FastAPI)


### Core Trust Endpoints
GET  /api/v1/agent/{address}
  Returns: trustScore, verdict, riskOutlook, tokenHealth, breakdown, flags, percentile
  Sources: Anubis ML + TronGrid behavioral + community reviews weighted 50/30/20

GET  /api/v1/agent/{address}/deep
  Returns everything above + monteCarlo, riskFlags[], tier, historicalScores[]


GET  /api/v1/agents?sort=trust&limit=50
  Returns leaderboard of all indexed agents


POST /api/v1/agent/register
  Body: { address, agentType, metadata }
  Calls TronTrustOracle.registerAgent + mints TrustPassport NFT
  Returns: { passportId, initialScore: 50, txHash }


### Token Safety
GET  /api/v1/token/{address}
  Returns: honeypot bool, liquidity, rugProbability, verdict, freezeFunction, mintFunction


### Community
GET  /api/v1/review?address={target}
  Returns: reviews[], avgRating, sentiment, reviewCount, topReview


POST /api/v1/review
  Body: { reviewerAddress, targetAddress, rating, comment }
  Claude API scores review quality before storing (filter spam/low-quality)
  Headers: X-TronTrust-Client required


POST /api/v1/review/vote
  Body: { reviewId, voterAddress, vote: "up"|"down" }


POST /api/v1/outcome
  Body: { queryId, outcome: "success"|"failure"|"partial"|"expired", reporter }
  Awards 5 Sun Points to reporter
  Feeds Anubis retraining pipeline


### Commercial Trust (TronTrust exclusive)
POST /api/v1/commercial/record-payment
  Body: { payer, payee, amountUsdt, daysToPayment, invoiceId, wasOverdue }
  Called by PayClaw after settlement
  Updates CommercialTrust.sol + recalculates composite trust score


GET  /api/v1/commercial/terms?buyer={addr}&merchant={addr}
  Returns: paymentWindowDays, requiresEscrow, creditLimitUsdt, reasoning


GET  /api/v1/commercial/relationship?a={addr}&b={addr}
  Returns full CommercialRelationship struct + score history


### Sentinel
GET  /api/v1/sentinel/alerts?severity=critical&limit=10
GET  /api/v1/monitor/alerts


### Threat Reporting (Collective Immunity — same as Maiat)
POST /api/v1/threat/report
  Body: { maliciousAddress, threatType, evidence, reporterAddress }
  3+ independent reports → auto-blacklist + score set to 0
  All TronTrust Guard users instantly block the address


### Scarab equivalent
GET  /api/v1/sunpoints?address={addr}
  Returns: balance, totalEarned, streak


POST /api/v1/sunpoints/claim
  Body: { address }
  Daily claim: +2 Sun Points


### Passport
GET  /api/v1/passport/{address}
  Returns full passport: trustScore, commercialScore, agentType,
  registeredAt, totalJobs, sunPoints, recentAttestations[]


GET  /api/v1/kya/{code}
  Know Your Agent lookup by short code


### x402 Paid Endpoints (same mechanic as Maiat, settled in USDT-TRC20 on Tron)
GET  /api/x402/trust?address=... — 0.02 USDT
GET  /api/x402/token-check?address=... — 0.01 USDT
GET  /api/x402/reputation?address=... — 0.03 USDT
POST /api/x402/token-forensics — 0.05 USDT
POST /api/x402/register-passport — 1.00 USDT


x402 flow: 402 response with TRC-20 payment requirement →
agent pays USDT to TronTrust treasury wallet →
retry with X-Payment header containing tx hash →
verify tx on TronGrid → serve response


---


## MCP Server (5 tools, same as Maiat)


File: mcp_server.py
Endpoint: expose via stdio or SSE


Tools:
1. get_agent_trust(address: str)
   Returns trust score, verdict, riskOutlook, breakdown


2. get_token_forensics(token_address: str)
   Returns deep token analysis: rug probability, honeypot, liquidity, ML score


3. get_agent_reputation(address: str)
   Returns community reviews, sentiment, avg rating, top reviews


4. report_outcome(query_id: str, outcome: str, reporter: str)
   Reports job outcome, earns 5 Sun Points for reporter


5. get_sun_points_balance(address: str)
   Returns Sun Points balance, streak, totalEarned


Config for agents:
```json
{
  "mcpServers": {
    "trontrust": {
      "url": "https://app.trontrust.io/api/mcp"
    }
  }
}
```


---


## TronTrust Guard SDK


Python package: trontrust-guard
Wraps any TronWeb/tronpy wallet with automatic trust checking.
