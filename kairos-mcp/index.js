#!/usr/bin/env node
const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { z } = require("zod");

const API = process.env.KAIROS_API_URL || "https://penn-blockathon-2026-production.up.railway.app/api/v1";

async function apiGet(path) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

const server = new McpServer({ name: "kairos", version: "1.0.0" });

server.tool("deploy_agent",
  "Deploy a new AI agent on Tron. Generates a real keypair, registers on the Oracle, and mints a soul-bound Passport NFT.",
  { name: z.string().describe("Name for the agent"), agent_type: z.enum(["trading", "defi", "payments", "data", "governance", "custom"]).describe("Type of agent") },
  async ({ name, agent_type }) => {
    const r = await apiPost("/arena/create-agent", { name, agentType: agent_type });
    return { content: [{ type: "text", text: JSON.stringify(r, null, 2) }] };
  }
);

server.tool("trust_send",
  "Send TRX from the TrustWallet. Checks recipient trust score on-chain first — blocked if below threshold.",
  { to: z.string().describe("Recipient Tron address"), amount_trx: z.number().describe("Amount of TRX") },
  async ({ to, amount_trx }) => {
    const r = await apiPost("/wallet/send", { to, amountTrx: amount_trx });
    return { content: [{ type: "text", text: JSON.stringify(r, null, 2) }] };
  }
);

server.tool("check_recipient",
  "Check if a recipient would pass the trust gate. Returns score, verdict, and ML risk flags.",
  { address: z.string().describe("Tron address to check") },
  async ({ address }) => {
    const r = await apiGet(`/wallet/check/${address}`);
    return { content: [{ type: "text", text: JSON.stringify(r, null, 2) }] };
  }
);

server.tool("set_min_trust",
  "Set minimum trust score for outgoing transfers (0-100).",
  { new_score: z.number().describe("New minimum score") },
  async ({ new_score }) => {
    const r = await apiPost("/wallet/set-min-trust", { newScore: new_score });
    return { content: [{ type: "text", text: JSON.stringify(r, null, 2) }] };
  }
);

server.tool("get_agent_trust",
  "Get full trust score, verdict, risk outlook, and breakdown for any Tron address.",
  { address: z.string().describe("Tron address") },
  async ({ address }) => {
    const r = await apiGet(`/agent/${address}`);
    return { content: [{ type: "text", text: JSON.stringify(r, null, 2) }] };
  }
);

server.tool("get_token_forensics",
  "Analyze a TRC-20 token for rug risk, honeypot, freeze/mint functions.",
  { token_address: z.string().describe("Token contract address") },
  async ({ token_address }) => {
    const r = await apiGet(`/token/${token_address}`);
    return { content: [{ type: "text", text: JSON.stringify(r, null, 2) }] };
  }
);

server.tool("wallet_stats",
  "Get TrustWallet stats: transfers, blocks, volume, current threshold.",
  {},
  async () => {
    const r = await apiGet("/wallet/stats");
    return { content: [{ type: "text", text: JSON.stringify(r, null, 2) }] };
  }
);

server.tool("lock_agent_permissions",
  "Lock an agent's Tron account via Account Permission Management. Protocol-level enforcement.",
  { agent_address: z.string().describe("Agent address to lock") },
  async ({ agent_address }) => {
    const r = await apiPost("/wallet/lock-permissions", { agentAddress: agent_address });
    return { content: [{ type: "text", text: JSON.stringify(r, null, 2) }] };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(console.error);
