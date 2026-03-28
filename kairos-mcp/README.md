# kairos-mcp

MCP server for [Kairos](https://kairosxyz.vercel.app) — trust infrastructure for AI agents on Tron.

## Quick Start

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "kairos": {
      "command": "npx",
      "args": ["-y", "kairos-mcp"]
    }
  }
}
```

That's it. Restart Claude and you'll have 8 tools for deploying agents, sending trust-gated payments, and managing trust policies on Tron.

## Tools

| Tool | Description |
|------|-------------|
| `deploy_agent` | Generate Tron keypair, register on Oracle, mint Passport NFT |
| `trust_send` | Send TRX with trust gate enforcement |
| `check_recipient` | Pre-send trust check with ML risk flags |
| `set_min_trust` | Update minimum trust threshold on-chain |
| `get_agent_trust` | Full trust score and breakdown |
| `get_token_forensics` | TRC-20 rug/honeypot analysis |
| `wallet_stats` | Transfer counts, blocks, volume |
| `lock_agent_permissions` | Lock wallet via Tron Account Permission Management |

## Example

> "Deploy a trading agent called AlphaBot"

Claude will call `deploy_agent` and return a real Tron address with TronScan links.

> "Send 1 TRX to TLyqzVGLV1srkB7dToTAEqgDSfPtXRJZYH"

Trust check runs on-chain. If score is below threshold, transfer is blocked.

## Custom API URL

By default, connects to the hosted Kairos backend. To use your own:

```json
{
  "mcpServers": {
    "kairos": {
      "command": "npx",
      "args": ["-y", "kairos-mcp"],
      "env": {
        "KAIROS_API_URL": "http://localhost:8000/api/v1"
      }
    }
  }
}
```
