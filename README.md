## Tube TLDR — Building The Best YouTube Summarizer

Welcome to Tube TLDR, a solo passion project with a bold mission: <br>
**Build the best YouTube summarizer on the internet.**

I tried the available tools online to summarize YouTube videos and didn’t like the experience — so I built my own. With Tube TLDR, I can choose the summary style I want, extend the workflow however I want, and keep improving it over time. And hypothetically, because you can run it with your own API keys, you can get a lot of usage for cheap.

No more scrubbing through hour-long videos — get the key takeaways fast.

## What Is Tube TLDR?

Tube TLDR takes a YouTube video and produces a concise, readable summary powered by modern AI. Whether it’s a long podcast, an educational lecture, or a tech review, Tube TLDR helps you extract the core ideas without watching the whole thing.

## Current Capabilities

- **Summarize YouTube videos** into clear, skimmable takeaways
- **Outline-driven summaries** for longer content (chapter/section style structure)
- **Works well for podcasts & lectures** where structure matters
- **Simple UI** for pasting a link and getting a result quickly
- **Improves readability** by focusing on the “so what?” (key points vs. transcript noise)

#### Built With

Python, Ollama Cloud / OpenAI & Streamlit <br>
Docker

## Running It

The default way to run Tube TLDR is via Streamlit:

```bash
streamlit run summarizer_ui.py
```

There are also a few extra helpers if you want to explore alternative ways to run or package it:

- **CLI** via `python -m src.cli` (non-interactive; see [Using the Command Line](#using-the-command-line))
- **MCP server** via `python -m src.mcp_server` (for AI agents; see [Using as an MCP Tool](#using-as-an-mcp-tool-for-ai-agents))
- **Optional local Whisper fallback** via `requirements-whisper.txt` (transcribes caption-less videos)
- **Streamlit UI** via `streamlit run summarizer_ui.py` (the default, interactive)
- **Dockerfile** for containerized runs
- **PyInstaller** launcher via `launcher.spec` (packages the Streamlit UI into a desktop executable)
- **Setup/Run scripts** (`setup.bat`, `run.bat`, `run.sh`) to bootstrap and run directly

### Using the Command Line

For scripts, cron jobs, and agents, `src.cli` summarizes a single video without
any prompts. It reads the same `config.yml` and environment as the UI, and keeps
stdout clean — only the summary (or the JSON payload) is printed there; all
progress and errors go to stderr.

```bash
python -m src.cli <url> [--style chapters|entire|one-sentence|shorts] \
                       [--language de,en] [--out PATH] [--json] \
                       [--config PATH] [--timeout SECONDS]
```

- `--style entire` (default) — whole-video bullet summary
- `--style chapters` — chapter-by-chapter summary (needs chapter markers)
- `--style one-sentence` — one-sentence TL;DR
- `--style shorts` — numbered short-form ideas per chapter (needs chapter markers)

`--out PATH` writes the markdown to a file instead of stdout; `--json` emits a
machine-readable object; `--language de,en` sets the transcript language
preference. Exit codes: `0` success, `1` config/IO error, `2` usage error or
timeout, `3` fetch failure, `4` summarization failure.

`--transcript-source auto|captions|whisper|force-whisper` controls where the
transcript comes from: `auto` (default) uses captions and falls back to local
Whisper only when captions are missing, `captions` never transcribes locally,
`whisper` transcribes only when captions are missing, and `force-whisper`
always transcribes locally. The same default lives in `config.yml` under
`transcription:` (`fallback`, `model`). The fallback needs the optional extras:
`pip install -r requirements-whisper.txt`.

Nightly example:

```bash
python -m src.cli "https://www.youtube.com/watch?v=..." --style entire --out /path/out.md
```

Using it as an agent tool instead? The MCP server exposes the same three summarize
tools to Copilot/Claude/Cursor — see
[docs/MCP.md](docs/MCP.md#cli-vs-mcp-server--which-one-when) for when to pick which.

### LLM Configuration

Tube TLDR supports two LLM backends, configured in `config.yml`:

- **Ollama Cloud** (preferred default) — uses [Ollama Cloud](https://ollama.com/cloud)
  with a paid Ollama account. Set `OLLAMA_API_KEY` in your `.env` file.
  Default model: `gpt-oss:120b`.
- **OpenAI** — uses the OpenAI API. Set `API_KEY` (or `OPENAI_API_KEY`) in your `.env` file.
  Default model: `gpt-4o-mini`.

In the Streamlit UI, you can switch providers, endpoints (Ollama Cloud vs. local),
and models in the sidebar. The model dropdown fetches the real list of available
models from your Ollama server.

### Using as an MCP Tool (for AI agents)

Tube TLDR includes an MCP (Model Context Protocol) server so that AI agents like
GitHub Copilot, opencode, Claude Desktop, or Cursor can summarize YouTube videos
as a tool call. Three tools are exposed:

- `summarize_by_chapters` — chapter-by-chapter summary (requires chapter markers)
- `summarize_entire_video` — whole-video summary as bullet points
- `summarize_one_sentence` — one-sentence TL;DR

Each tool takes a `url` (and optional `language`) and handles video fetching internally.

**VS Code / GitHub Copilot:** The `.vscode/mcp.json` file is already configured.
Restart VS Code (or reload the window) and the tools will appear in Copilot Chat.

**opencode / Claude Desktop / Cursor:** Add the server to your agent's MCP config:

```json
{
  "mcpServers": {
    "tube-tldr": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/Tube-TLDR"
    }
  }
}
```

The MCP server reads `config.yml` and environment variables at startup, so it
uses the same LLM provider/model as the Streamlit UI.

## Documentation

- [docs/MCP.md](docs/MCP.md) — MCP server setup and the tools it exposes.
- [docs/RUNBOOK.md](docs/RUNBOOK.md) — VPS deployment, the residential-proxy requirement, cron/systemd, and monitoring.

## Known limitations

- **Playlists are not supported yet.** `src.cli` summarizes a single video URL; a nightly playlist watcher is on the roadmap.
- **A residential proxy is required on datacenter IPs.** YouTube blocks most cloud-provider ranges — see [docs/RUNBOOK.md](docs/RUNBOOK.md).
- **Caption-less videos need the optional Whisper extras.** Without `requirements-whisper.txt` installed, a video with no captions still fails with exit code `3` (the old behavior). With the extras installed, `transcription.fallback: auto` transcribes it locally instead.
- **The Whisper fallback's yt-dlp download ignores `config.yml` proxy settings.** The proxy is only applied to the YouTube-transcript/metadata path, so on a datacenter IP the audio download may still be blocked — see [docs/RUNBOOK.md](docs/RUNBOOK.md).
- **Shorts generation is experimental.** It lives in a separate module and output quality varies.
- **Long videos (>45–60 min) are summarized in a single LLM call.** Chunked map-reduce is on the roadmap.

### Shoutout

If you find this useful, consider starring ⭐ the repo or sharing it with someone who drowns in YouTube videos daily.

### Roadmap / Ideas (moving to Issues soon)

- display more infos in the UI (log messages)
- implement summaries for short videos without an outline
- write a function to get a dedicated chapter headline when synthetically generated