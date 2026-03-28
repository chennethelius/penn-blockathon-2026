"""Arena endpoints — live demo of trust-gated agent economy on Nile testnet."""

import os
import json
import time
import logging
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from typing import Optional
import httpx
from tronpy.keys import PrivateKey
from app.services.contracts import get_contracts
from app.services import anubis_client

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Rate limiting: max 10 commands per minute per IP
_rate_limit: dict[str, list[float]] = {}
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 60  # seconds

router = APIRouter()

# ── Event log: captures all activity from any source (Arena UI, MCP, API) ──
_event_log: list[dict] = []
MAX_EVENTS = 100


def log_event(event_type: str, message: str, tx_hash: str = "", source: str = "api"):
    """Append an event visible to the Arena live feed."""
    _event_log.insert(0, {
        "type": event_type,  # approved, blocked, info, register
        "message": message,
        "txHash": tx_hash,
        "source": source,  # arena, mcp, api
        "timestamp": time.time(),
    })
    if len(_event_log) > MAX_EVENTS:
        _event_log.pop()


# Pre-seeded agents — same addresses as scripts/seed_agents.py
# Run `python scripts/seed_agents.py` before the demo to register + set scores on-chain.
ARENA_AGENTS = [
    {"address": "TLyqzVGLV1srkB7dToTAEqgDSfPtXRJZYH", "name": "Coinbase Pay",    "type": "payments",   "emoji": "\U0001f4b0", "defaultScore": 85},
    {"address": "TX5ug3U97zsLdaNTfS5d89WJXTbvthjYPq", "name": "Aave Lend",        "type": "defi",       "emoji": "\U0001f3e6", "defaultScore": 72},
    {"address": "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9", "name": "Stripe Agent",     "type": "payments",   "emoji": "\U0001f4b3", "defaultScore": 43},
    {"address": "TAUN6FwrnwwmaEqYcckffC7wYmbaS6cBiX", "name": "Delve",            "type": "custom",     "emoji": "\U0001f47e", "defaultScore": 12},
]

# Persist deployed agents to a JSON file so they survive restarts
_AGENTS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "arena_agents.json")


def _load_session_agents() -> list[dict]:
    try:
        with open(_AGENTS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_session_agents(agents: list[dict]):
    try:
        with open(_AGENTS_FILE, "w") as f:
            json.dump(agents, f, indent=2)
    except Exception as e:
        logger.warning("Could not save agents: %s", e)


_session_agents: list[dict] = _load_session_agents()


@router.get("/arena/agents")
async def get_arena_agents():
    """Return all arena agents with live on-chain trust scores."""
    contracts = get_contracts()
    all_agents = ARENA_AGENTS + _session_agents

    result = []
    for agent in all_agents:
        score = agent["defaultScore"]
        on_chain = False

        if contracts.is_ready:
            try:
                trust = contracts.get_trust(agent["address"])
                if trust.get("on_chain") and trust["score"] > 0:
                    score = trust["score"]
                    on_chain = True
            except Exception:
                pass

        result.append({
            "address": agent["address"],
            "name": agent["name"],
            "type": agent["type"],
            "emoji": agent["emoji"],
            "score": score,
            "onChain": on_chain,
        })

    # Get wallet stats for current min threshold
    min_score = 40
    wallet_address = ""
    try:
        stats = contracts.wallet_get_stats()
        min_score = stats.get("currentMinScore", 40)
        wallet_address = "TFD31Cr3PfZPZjPHUWSVstkZ53ZCEyX6yi"
    except Exception:
        pass

    return {
        "agents": result,
        "walletAddress": wallet_address,
        "minTrustScore": min_score,
    }


class CreateAgentRequest(BaseModel):
    name: str
    agentType: str


class CreateAgentResponse(BaseModel):
    success: bool
    address: str = ""
    name: str = ""
    agentType: str = ""
    score: int = 50
    oracleTxHash: str = ""
    passportTxHash: str = ""
    error: Optional[str] = None


@router.post("/arena/create-agent", response_model=CreateAgentResponse)
async def create_arena_agent(req: CreateAgentRequest):
    """Generate a real Tron keypair, register on Oracle, and mint Passport NFT."""
    contracts = get_contracts()

    if not contracts.is_ready:
        return CreateAgentResponse(
            success=False,
            error="Contracts not configured. Check .env and start the backend.",
        )

    # Generate a real Tron keypair
    priv = PrivateKey.random()
    address = priv.public_key.to_base58check_address()

    # Register on Oracle
    oracle_tx = ""
    try:
        oracle_tx = contracts.register_agent(address, req.agentType)
    except Exception as e:
        return CreateAgentResponse(
            success=False,
            address=address,
            error=f"Oracle registration failed: {e}",
        )

    # Set initial score to 50 on-chain
    try:
        contracts.update_score(address, 50, "CAUTION")
    except Exception:
        pass

    # Mint Passport NFT
    passport_tx = ""
    try:
        passport_tx = contracts.mint_passport(address, req.agentType)
    except Exception:
        pass  # Non-fatal — passport mint can fail without breaking the demo

    # Determine emoji
    type_emojis = {
        "trading": "\U0001f4c8", "defi": "\U0001f3e6", "payments": "\U0001f4b3",
        "data": "\U0001f4ca", "governance": "\U0001f3db", "custom": "\u26a1",
    }

    agent_data = {
        "address": address,
        "name": req.name,
        "type": req.agentType,
        "emoji": type_emojis.get(req.agentType, "\u26a1"),
        "defaultScore": 50,
    }
    _session_agents.append(agent_data)
    _save_session_agents(_session_agents)

    log_event("register", f"{req.name} registered as {req.agentType} agent (score 50)", oracle_tx, "arena")
    if passport_tx:
        log_event("register", f"{req.name} Passport NFT minted", passport_tx, "mcp")

    return CreateAgentResponse(
        success=True,
        address=address,
        name=req.name,
        agentType=req.agentType,
        score=50,
        oracleTxHash=oracle_tx,
        passportTxHash=passport_tx,
    )


@router.get("/arena/events")
async def get_arena_events(since: float = Query(0)):
    """Return recent events, optionally filtered to those after a timestamp."""
    if since > 0:
        return {"events": [e for e in _event_log if e["timestamp"] > since]}
    return {"events": _event_log[:50]}


# ═══════════════════════════════════════════════════════════════════
#  Groq-powered natural language command interpreter
# ═══════════════════════════════════════════════════════════════════

ARENA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "deploy_agent",
            "description": "Deploy a new AI agent on the Tron blockchain. Generates a wallet, registers on the Oracle, and mints a Passport NFT.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name for the agent"},
                    "agent_type": {"type": "string", "enum": ["trading", "defi", "payments", "data", "governance", "custom"], "description": "Type of agent"},
                },
                "required": ["name", "agent_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_trx",
            "description": "Send TRX from the TrustWallet to a recipient agent. The wallet checks the recipient's trust score first — if below the threshold, the transfer is blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_name": {"type": "string", "description": "Name of the recipient agent"},
                    "amount": {"type": "number", "description": "Amount of TRX to send"},
                },
                "required": ["recipient_name", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_min_trust",
            "description": "Set the minimum trust score required for outgoing transfers from the TrustWallet. Agents below this score will be blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "description": "Minimum trust score (0-100)"},
                },
                "required": ["score"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_agent",
            "description": "Check an agent's trust score and whether they would pass the trust gate for receiving transfers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Name of the agent to check"},
                },
                "required": ["agent_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "paid_lookup",
            "description": "Demo the x402 paid API flow. Shows what happens when an agent calls the monetized trust API: first a 402 Payment Required response with pricing, then after payment the trust data is returned. Use this when the user asks about paid API, x402, monetization, or paying for a lookup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Name of the agent to look up via paid API"},
                },
                "required": ["agent_name"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are the TronTrust Arena command interpreter. You help users manage AI agents on the Tron blockchain.

Available agents: {agents}

Current minimum trust score threshold: {threshold}

Interpret the user's natural language command and call the appropriate tool. If the user's intent is unclear, ask for clarification in a brief response. Always pick the most likely tool — don't be overly cautious. Keep text responses under 2 sentences."""


def _find_agent_by_name(name: str) -> Optional[dict]:
    """Find an agent by fuzzy name match."""
    all_agents = ARENA_AGENTS + _session_agents
    n = name.lower().strip()
    # Exact match first
    for a in all_agents:
        if a["name"].lower() == n:
            return a
    # Partial match
    for a in all_agents:
        if n in a["name"].lower() or a["name"].lower() in n:
            return a
    return None


async def _exec_deploy(args: dict) -> dict:
    """Execute deploy_agent tool call."""
    req = CreateAgentRequest(name=args["name"], agentType=args["agent_type"])
    result = await create_arena_agent(req)
    return result.model_dump()


async def _exec_send(args: dict) -> dict:
    """Execute send_trx tool call."""
    agent = _find_agent_by_name(args["recipient_name"])
    if not agent:
        return {"success": False, "error": f"Agent '{args['recipient_name']}' not found"}

    address = agent["address"]
    amount = args["amount"]

    # Check trust first
    contracts = get_contracts()
    prediction = await anubis_client.predict_agent(address)
    risk_flags = set(prediction.get("risk_flags", []))
    deny_flags = {"wash_trading_detected", "circular_payments", "honeypot_risk",
                  "energy_drain_attacker", "phishing_association", "address_poisoning"}
    blocked_flags = risk_flags & deny_flags

    if blocked_flags:
        log_event("blocked", f"TrustWallet → {agent['name']} blocked by ML: {', '.join(blocked_flags)}", "", "arena")
        return {"success": False, "blocked": True, "recipientName": agent["name"],
                "recipientScore": prediction.get("ml_score"), "reason": f"ML risk flags: {', '.join(blocked_flags)}"}

    check = contracts.wallet_check_recipient(address) if contracts.is_ready else {"score": agent.get("defaultScore", 50), "wouldPass": agent.get("defaultScore", 50) >= 40, "minRequired": 40}

    if not check["wouldPass"]:
        log_event("blocked", f"TrustWallet → {agent['name']} blocked: score {check['score']} < min {check['minRequired']}", "", "arena")
        return {"success": False, "blocked": True, "recipientName": agent["name"],
                "recipientScore": check["score"], "minRequired": check["minRequired"],
                "reason": f"Score {check['score']} below minimum {check['minRequired']}"}

    # Execute send
    if not contracts.is_ready:
        return {"success": False, "error": "Contracts not configured — check .env", "recipientName": agent["name"]}
    try:
        amount_sun = int(amount * 1_000_000)
        tx_hash = contracts.wallet_send(address, amount_sun)
        if not tx_hash:
            return {"success": False, "error": "Transaction returned no hash — TrustWallet may be out of TRX. Fund it at TFD31Cr3PfZPZjPHUWSVstkZ53ZCEyX6yi on Nile.", "recipientName": agent["name"]}
        log_event("approved", f"TrustWallet → {agent['name']} sent {amount} TRX (score {check['score']})", tx_hash, "arena")
        return {"success": True, "recipientName": agent["name"], "recipientScore": check["score"],
                "amount": amount, "txHash": tx_hash, "address": address}
    except Exception as e:
        err = str(e)
        if "balance" in err.lower() or "insufficient" in err.lower() or "not enough" in err.lower():
            return {"success": False, "error": f"TrustWallet out of TRX. Fund TFD31Cr3PfZPZjPHUWSVstkZ53ZCEyX6yi on Nile faucet.", "recipientName": agent["name"]}
        return {"success": False, "error": err, "recipientName": agent["name"]}


async def _exec_set_threshold(args: dict) -> dict:
    """Execute set_min_trust tool call."""
    score = max(0, min(100, args["score"]))
    contracts = get_contracts()
    try:
        tx_hash = contracts.wallet_set_min_trust(score) if contracts.is_ready else ""
        log_event("info", f"Min trust threshold → {score}", tx_hash, "arena")
        return {"success": True, "newScore": score, "txHash": tx_hash}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _exec_check(args: dict) -> dict:
    """Execute check_agent tool call."""
    agent = _find_agent_by_name(args["agent_name"])
    if not agent:
        return {"success": False, "error": f"Agent '{args['agent_name']}' not found"}

    address = agent["address"]
    contracts = get_contracts()
    check = contracts.wallet_check_recipient(address) if contracts.is_ready else {"score": agent.get("defaultScore", 50), "wouldPass": True, "minRequired": 40}

    prediction = await anubis_client.predict_agent(address)

    return {
        "success": True,
        "name": agent["name"],
        "address": address,
        "onChainScore": check["score"],
        "minRequired": check["minRequired"],
        "wouldPass": check["wouldPass"],
        "riskFlags": prediction.get("risk_flags", []),
        "verdict": "APPROVED" if check["wouldPass"] else "BLOCKED",
    }


async def _exec_paid_lookup(args: dict) -> dict:
    """Demo the x402 paid API flow with a real TRX payment on-chain."""
    agent = _find_agent_by_name(args["agent_name"])
    if not agent:
        return {"success": False, "error": f"Agent '{args['agent_name']}' not found"}

    address = agent["address"]
    price_trx = 0.1  # Demo price in TRX (stands in for 0.02 USDT)
    contracts = get_contracts()

    # Step 1: the 402 response
    payment_required = {
        "status": 402,
        "message": "Payment Required",
        "endpoint": "/api/x402/trust",
        "amount": "0.02 USDT (demo: 0.1 TRX)",
        "payTo": contracts._operator if contracts.is_ready else "treasury",
    }

    # Step 2: make the real payment (TrustWallet → operator as "API fee")
    payment_tx = ""
    payment_error = ""
    if contracts.is_ready and contracts._operator:
        try:
            amount_sun = int(price_trx * 1_000_000)
            payment_tx = contracts.wallet_send(contracts._operator, amount_sun)
            if not payment_tx:
                payment_error = "TrustWallet out of TRX — fund TFD31Cr3PfZPZjPHUWSVstkZ53ZCEyX6yi on Nile faucet"
        except Exception as e:
            payment_error = f"Payment failed: {e}"
    elif not contracts.is_ready:
        payment_error = "Contracts not configured"

    # Step 3: get the trust data (the "paid" response)
    from app.routers.trust import _build_trust_profile
    profile = await _build_trust_profile(address)

    log_event("info", f"x402 paid lookup: {agent['name']} (0.1 TRX fee)", payment_tx, "arena")

    return {
        "success": True,
        "name": agent["name"],
        "address": address,
        "priceTrx": price_trx,
        "paymentTxHash": payment_tx,
        "paymentError": payment_error,
        "paymentRequired": payment_required,
        "trustData": {
            "trustScore": profile["trustScore"],
            "verdict": profile["verdict"].value if hasattr(profile["verdict"], "value") else str(profile["verdict"]),
            "riskOutlook": profile["riskOutlook"],
            "breakdown": profile["breakdown"],
            "flags": profile["flags"],
        },
    }


TOOL_EXECUTORS = {
    "deploy_agent": _exec_deploy,
    "send_trx": _exec_send,
    "set_min_trust": _exec_set_threshold,
    "check_agent": _exec_check,
    "paid_lookup": _exec_paid_lookup,
}


class CommandRequest(BaseModel):
    message: str


@router.post("/arena/command")
async def arena_command(req: CommandRequest, request: Request):
    """Interpret a natural language command via Groq LLM and execute it."""
    # Rate limit
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    hits = _rate_limit.get(ip, [])
    hits = [t for t in hits if now - t < RATE_LIMIT_WINDOW]
    if len(hits) >= RATE_LIMIT_MAX:
        return {"reply": f"Rate limited — max {RATE_LIMIT_MAX} commands per minute. Try again shortly."}
    hits.append(now)
    _rate_limit[ip] = hits

    if not GROQ_API_KEY:
        return {"error": "GROQ_API_KEY not set", "reply": "LLM not configured. Add GROQ_API_KEY to .env."}

    # Build agent context for the system prompt
    all_agents = ARENA_AGENTS + _session_agents
    agent_summary = ", ".join(f"{a['name']} (score {a['defaultScore']})" for a in all_agents)
    contracts = get_contracts()
    threshold = 40
    try:
        if contracts.is_ready:
            stats = contracts.wallet_get_stats()
            threshold = stats.get("currentMinScore", 40)
    except Exception:
        pass

    system = SYSTEM_PROMPT.format(agents=agent_summary, threshold=threshold)

    # Call Groq
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": req.message},
                    ],
                    "tools": ARENA_TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.1,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error("Groq API error: %s", e)
        return {"error": str(e), "reply": f"LLM error: {e}"}

    choice = data["choices"][0]
    msg = choice["message"]

    # If no tool call, return the text reply
    if not msg.get("tool_calls"):
        return {"reply": msg.get("content", "I'm not sure what to do. Try: deploy, send, set threshold, or check an agent.")}

    # Execute the tool call
    tool_call = msg["tool_calls"][0]
    fn_name = tool_call["function"]["name"]
    fn_args = json.loads(tool_call["function"]["arguments"])

    executor = TOOL_EXECUTORS.get(fn_name)
    if not executor:
        return {"reply": f"Unknown action: {fn_name}"}

    result = await executor(fn_args)
    return {"tool": fn_name, "args": fn_args, "result": result}
