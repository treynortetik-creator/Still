# still-mcp

MCP (Model Context Protocol) server for the [Still](https://github.com/treynortetik-creator/Still) content multiplier platform.

Exposes Still's content library, remixing, editing, export, brand voice, personas, and batch processing as MCP tools consumable by any MCP-compatible AI client (Claude Desktop, Claude Code, etc.).

## Tools

| Tool | Description |
|---|---|
| `get_library` | Browse & filter the content library (stills) |
| `get_library_stats` | Aggregate library stats: totals, by-type counts, most-used |
| `remix_content` | Generate new content from selected stills |
| `remix_search` | Search stills by topic keyword before remixing |
| `edit_content` | Apply plain-language editing instructions to an output |
| `adjust_tone` | Apply a tone preset to an output |
| `save_edit` | Persist edited content and record it in edit history |
| `export_content` | Export a job's outputs as JSON or Markdown |
| `get_brand_voice` | Retrieve brand voice profile (and optionally config) |
| `list_personas` | List available target personas (default + custom) |
| `get_batch_status` | Check processing status of a batch upload |
| `get_tone_presets` | List all available tone presets |

## Setup

### Prerequisites

- Node.js ≥ 18
- A running Still backend (local or deployed)

### Install & build

```bash
cd mcp-server
npm install
npm run build
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `STILL_URL` | Yes | Base URL of the Still API, e.g. `https://your-app.railway.app` |
| `STILL_API_KEY` | Yes | JWT bearer token for an authenticated Still user |

## Claude Desktop configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the equivalent path on your platform:

```json
{
  "mcpServers": {
    "still": {
      "command": "node",
      "args": ["/absolute/path/to/mcp-server/dist/index.js"],
      "env": {
        "STILL_URL": "https://your-app.railway.app",
        "STILL_API_KEY": "your-jwt-token"
      }
    }
  }
}
```

## Claude Code configuration

A `.mcp.json` file is included at the repo root. Set the env vars in your shell or `.env`:

```bash
export STILL_URL=https://your-app.railway.app
export STILL_API_KEY=your-jwt-token
```

Then Claude Code will pick up the MCP server automatically.

## Authentication

All Still API endpoints require a JWT bearer token. Obtain one by logging in to the Still app and copying the access token from your browser's local storage or network requests. Pass it as `STILL_API_KEY`.

## Development

```bash
npm run dev   # watch mode TypeScript compilation
```
