#!/usr/bin/env node
const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");

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

const TOOLS = [
  { name: "deploy_agent", description: "Deploy a new AI agent on Tron. Generates a real keypair, registers on the Oracle, and mints a soul-bound Passport NFT.", inputSchema: { type: "object", properties: { name: { type: "string", description: "Name for the agent" }, agent_type: { type: "string", enum: ["trading", "defi", "payments", "data", "governance", "custom"], description: "Type of agent" } }, required: ["name", "agent_type"] } },
  { name: "trust_send", description: "Send TRX from the TrustWallet. Checks recipient trust score on-chain first — blocked if below threshold.", inputSchema: { type: "object", properties: { to: { type: "string", description: "Recipient Tron address" }, amount_trx: { type: "number", description: "Amount of TRX" } }, required: ["to", "amount_trx"] } },
  { name: "check_recipient", description: "Check if a recipient would pass the trust gate. Returns score, verdict, and ML risk flags.", inputSchema: { type: "object", properties: { address: { type: "string", description: "Tron address to check" } }, required: ["address"] } },
  { name: "set_min_trust", description: "Set minimum trust score for outgoing transfers (0-100).", inputSchema: { type: "object", properties: { new_score: { type: "integer", description: "New minimum score" } }, required: ["new_score"] } },
  { name: "get_agent_trust", description: "Get full trust score, verdict, risk outlook, and breakdown for any Tron address.", inputSchema: { type: "object", properties: { address: { type: "string", description: "Tron address" } }, required: ["address"] } },
  { name: "get_token_forensics", description: "Analyze a TRC-20 token for rug risk, honeypot, freeze/mint functions.", inputSchema: { type: "object", properties: { token_address: { type: "string", description: "Token contract address" } }, required: ["token_address"] } },
  { name: "wallet_stats", description: "Get TrustWallet stats: transfers, blocks, volume, current threshold.", inputSchema: { type: "object", properties: {} } },
  { name: "lock_agent_permissions", description: "Lock an agent's Tron account via Account Permission Management. Protocol-level enforcement.", inputSchema: { type: "object", properties: { agent_address: { type: "string", description: "Agent address to lock" } }, required: ["agent_address"] } },
];

const server = new Server({ name: "kairos", version: "1.0.0" }, { capabilities: { tools: {} } });

server.setRequestHandler({ method: "tools/list" }, async () => ({ tools: TOOLS }));

server.setRequestHandler({ method: "tools/call" }, async (request) => {
  const { name, arguments: args } = request.params;
  let result;

  try {
    switch (name) {
      case "deploy_agent":
        result = await apiPost("/arena/create-agent", { name: args.name, agentType: args.agent_type });
        break;
      case "trust_send":
        result = await apiPost("/wallet/send", { to: args.to, amountTrx: args.amount_trx });
        break;
      case "check_recipient":
        result = await apiGet(`/wallet/check/${args.address}`);
        break;
      case "set_min_trust":
        result = await apiPost("/wallet/set-min-trust", { newScore: args.new_score });
        break;
      case "get_agent_trust":
        result = await apiGet(`/agent/${args.address}`);
        break;
      case "get_token_forensics":
        result = await apiGet(`/token/${args.token_address}`);
        break;
      case "wallet_stats":
        result = await apiGet("/wallet/stats");
        break;
      case "lock_agent_permissions":
        result = await apiPost("/wallet/lock-permissions", { agentAddress: args.agent_address });
        break;
      default:
        result = { error: `Unknown tool: ${name}` };
    }
  } catch (e) {
    result = { error: e.message };
  }

  return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(console.error);
