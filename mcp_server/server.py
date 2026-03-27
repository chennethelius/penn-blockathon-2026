"""TronTrust MCP Server — 5 tools for AI agents.

Tools:
  1. get_agent_trust     — trust score + verdict + breakdown
  2. get_token_forensics — deep token analysis (rug prob, honeypot, freeze)
  3. get_agent_reputation — community reviews + sentiment
  4. report_outcome      — report job outcome, earn 5 Sun Points
  5. get_sun_points_balance — Sun Points balance + streak

Run:
  python mcp_server/server.py                     # stdio mode
  python mcp_server/server.py --transport sse      # SSE mode (for web)

Config for agents:
  {
    "mcpServers": {
      "trontrust": {
        "command": "python",
        "args": ["mcp_server/server.py"]
      }
    }
  }
"""

import os
import sys
import json
import asyncio
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

API_BASE = os.getenv("TRONTRUST_API_BASE", "http://localhost:8000/api/v1")
TIMEOUT = 15.0

app = Server("trontrust")


async def _api_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{API_BASE}{path}")
        resp.raise_for_status()
        return resp.json()


async def _api_post(path: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{API_BASE}{path}", json=data)
        resp.raise_for_status()
        return resp.json()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_agent_trust",
            description="Get trust score (0-100), verdict, risk outlook, and breakdown for any Tron wallet address. Use this before transacting with an unknown agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Tron wallet address (base58, starts with T)",
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="get_token_forensics",
            description="Analyze a TRC-20 token for rug pull risk. Returns honeypot detection, freeze/mint authority, rug probability, and verdict.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token_address": {
                        "type": "string",
                        "description": "TRC-20 token contract address",
                    }
                },
                "required": ["token_address"],
            },
        ),
        Tool(
            name="get_agent_reputation",
            description="Get community reviews, average rating, sentiment, and review count for a Tron wallet address.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Tron wallet address to check reputation for",
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="report_outcome",
            description="Report the outcome of a job or transaction. Earns 5 Sun Points for the reporter. Feeds the ML retraining pipeline.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_id": {
                        "type": "string",
                        "description": "ID of the original trust query or transaction",
                    },
                    "outcome": {
                        "type": "string",
                        "enum": ["success", "failure", "partial", "expired"],
                        "description": "Outcome of the job",
                    },
                    "reporter": {
                        "type": "string",
                        "description": "Tron address of the reporter",
                    },
                },
                "required": ["query_id", "outcome", "reporter"],
            },
        ),
        Tool(
            name="get_sun_points_balance",
            description="Check Sun Points balance, total earned, and daily streak for a wallet address.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Tron wallet address",
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="register_agent",
            description="Register a new AI agent on TronTrust. Creates an on-chain AgentProfile on TronTrustOracle and mints a soul-bound TrustPassport NFT. Initial trust score is 50.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Tron wallet address of the agent to register",
                    },
                    "agent_type": {
                        "type": "string",
                        "description": "Type of agent (e.g. 'DeFi Bot', 'Trading Agent', 'Payment Agent')",
                    },
                },
                "required": ["address", "agent_type"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_agent_trust":
            result = await _api_get(f"/agent/{arguments['address']}")
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )]

        elif name == "get_token_forensics":
            result = await _api_get(f"/token/{arguments['token_address']}")
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )]

        elif name == "get_agent_reputation":
            result = await _api_get(f"/review?address={arguments['address']}")
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )]

        elif name == "report_outcome":
            result = await _api_post("/outcome", {
                "queryId": arguments["query_id"],
                "outcome": arguments["outcome"],
                "reporter": arguments["reporter"],
            })
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )]

        elif name == "get_sun_points_balance":
            result = await _api_get(f"/sunpoints?address={arguments['address']}")
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )]

        elif name == "register_agent":
            result = await _api_post("/agent/register", {
                "address": arguments["address"],
                "agentType": arguments["agent_type"],
            })
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except httpx.HTTPStatusError as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"API returned {e.response.status_code}", "detail": e.response.text}),
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)}),
        )]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
