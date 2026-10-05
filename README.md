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

- **Dockerfile** for containerized runs
- **PyInstaller** setup via `launcher.spec`
- **Headless mode** via `headless.py`
- **Setup/Run scripts** (`setup.bat`, `run.bat`, `run.sh`) to bootstrap and run directly

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

### Shoutout

If you find this useful, consider starring ⭐ the repo or sharing it with someone who drowns in YouTube videos daily.

### Roadmap / Ideas (moving to Issues soon)

- display more infos in the UI (log messages)
- implement summaries for short videos without an outline
- write a function to get a dedicated chapter headline when synthetically generated