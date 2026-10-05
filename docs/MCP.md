# MCP Server

Tube-TLDR ships a [Model Context Protocol](https://modelcontextprotocol.io) server
that exposes its YouTube summarization as tools any MCP-compatible agent can call
(GitHub Copilot, opencode, Claude Desktop, Cursor, …).

The server speaks **stdio** — no HTTP port, no daemon. The client launches it as a
subprocess and talks JSON-RPC over stdin/stdout.

```
python -m src.mcp_server
```

Each tool fetches the video itself; callers only pass a URL.

## CLI vs MCP server — which one when?

Both wrap the same summarizer core (`src/transcribe_summarize.py`). The difference is
who drives the process:

| | CLI (`python -m src.cli`) | MCP server (`python -m src.mcp_server`) |
|---|---|---|
| Caller | You, scripts, cron/systemd | An LLM agent (GitHub Copilot, Claude Desktop, Cursor) |
| Transport | One process: argv in → text/exit code out | Persistent stdio JSON-RPC session |
| Made for | Automation: nightly jobs on a VPS, batch runs, piping output to files, CI | Conversational use: "summarize this video" as a tool call during a chat |
| Output | stdout (human markdown) / `--out` file / `--json` for programs | Tool-call result text back to the agent |
| Setup | Nothing persistent — runs and exits | Client config (`.vscode/mcp.json` or agent JSON config) |

Rule of thumb: **anything that runs without a human at a keyboard → CLI. Anything an
AI agent should do for you mid-chat → MCP.**

## Tools

| Tool | What it does | When to use it |
|------|--------------|----------------|
| `summarize_by_chapters` | Splits the video by its chapter markers and returns a bullet-point summary per chapter, with timestamps. | Longer videos that have chapters in the description. Errors if the video has no chapters. |
| `summarize_entire_video` | One bullet-point summary covering the whole transcript. | Shorter videos, or when you want a single overview regardless of chapters. |
| `summarize_one_sentence` | A single-sentence TL;DR, with the video title as a heading. | A quick gist. |

All three take the same arguments:

| Argument | Required | Description |
|----------|----------|-------------|
| `url` | yes | YouTube URL (`watch`, `youtu.be`, `shorts`, or `embed` form). |
| `language` | no | Preferred transcript language code (e.g. `en`, `de`). Defaults to `['de', 'en']`. |

All three are annotated `readOnlyHint: true`, `idempotentHint: true`,
`openWorldHint: true` — they read public YouTube pages and call your LLM, and write
no files.

## Experimental tools

| Tool | What it does | When to use it |
|------|--------------|----------------|
| `generate_shorts_scripts` | Generates a short-form (Shorts / Reels / TikTok) voiceover script per chapter. | You want draft short-form scripts. **Requires chapter markers** — errors otherwise. |

`generate_shorts_scripts` takes the same arguments as the core tools (`url`
required, `language` optional) and carries the same read-only annotations.

> **Experimental.** Quality varies and the prompts are still being tuned. The
> chapter-less crash is guarded (returns `isError: true`), but treat the output as
> a draft, not a finished script.

There is also a standalone experimental CLI:

```
python -m src.shorts_cli <url> [--language de,en] [--out PATH] [--config PATH]
```

It is deliberately decoupled from `src.cli` so the experimental path can change
without touching the stable product.

## Configuration

The server reads the same config as the Streamlit UI:

- **`config.yml`** — LLM provider/model/base URL and proxy settings.
- **`.env`** — API keys (`OLLAMA_API_KEY`, `OPENAI_API_KEY`, …). The server calls
  `dotenv.load_dotenv()` at startup, so `python -m src.mcp_server` works standalone
  from the repo root. MCP clients that pass `env` explicitly still work.

| Environment variable | Default | Purpose |
|----------------------|---------|---------|
| `TUBE_TLDR_TOOL_TIMEOUT_S` | `900` | Per-tool wall-clock budget in seconds. Video fetch + summarization are network-bound; this is the stall guard. |

## Client configuration

### VS Code (`mcp.json`)

```json
{
  "servers": {
    "tube-tldr": {
      "type": "stdio",
      "command": "/home/tim/Vault/Repositories/Tube-TLDR/Tube-TLDR/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/home/tim/Vault/Repositories/Tube-TLDR/Tube-TLDR"
    }
  }
}
```

### Generic JSON (Claude Desktop, Cursor, …)

```json
{
  "mcpServers": {
    "tube-tldr": {
      "command": "/home/tim/Vault/Repositories/Tube-TLDR/Tube-TLDR/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/home/tim/Vault/Repositories/Tube-TLDR/Tube-TLDR"
    }
  }
}
```

Point `command` at the interpreter that has the dependencies installed (the repo's
`.venv`), and set `cwd` to the repo root so `config.yml` and `.env` resolve.

## Error behavior

Failures are returned as a `CallToolResult` with **`isError: true`**, not as a
successful result whose text happens to start with "Error". Clients that respect the
flag will surface the call as failed.

- **Missing/invalid `url`** → `isError: true` (the SDK's schema validation also
  rejects a missing `url` before the handler runs).
- **Fetch failure** (bad URL, no transcript, network error) → `isError: true`.
- **Summarization failure** (LLM error) → `isError: true`.
- **Unknown tool name** → `isError: true`.
- **Timeout** → `isError: true`, message `timed out after <N>s — video
  fetch+summarization took too long`. Raise `TUBE_TLDR_TOOL_TIMEOUT_S` for very long
  videos.

## Privacy

The server fetches **public** YouTube pages and transcripts, and sends the transcript
text to **your configured LLM provider** (whatever `config.yml` points at — a local
Ollama server, Ollama Cloud, or OpenAI). Nothing is written to disk by the tools. If
you point it at a cloud provider, transcript text leaves your machine.
