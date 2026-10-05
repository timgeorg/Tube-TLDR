# Runbook — Deploying Tube-TLDR on a VPS

**Goal:** run Tube-TLDR unattended on a VPS (nightly, via cron or a systemd
timer) so it summarizes videos into markdown files without a human in the loop.

This document exists mainly for one reason: **a VPS almost always needs a
residential proxy.** Read section 1 before anything else.

---

## 1. Residential proxy requirement (CRITICAL — read first)

YouTube aggressively blocks requests from datacenter / cloud-provider IP
ranges — AWS, GCP, Azure, Hetzner, DigitalOcean, Linode, OVH, and friends. From
those IPs you typically get one of:

- HTTP `429 Too Many Requests` on the watch page,
- an empty or missing transcript list,
- a consent / "sign in to confirm you're not a bot" interstitial instead of the
  video page.

Tube-TLDR fetches the watch page with `requests` and the transcript with
`youtube-transcript-api`. Both honour the proxy configured in `config.yml`, so
the fix is to route them through a **residential** endpoint.

### Configure it

`config.yml`:

```yaml
proxy:
  enabled: true
  http:  socks5h://user:pass@residential-host:1080
  https: socks5h://user:pass@residential-host:1080
```

Notes:

- Set **both** `http` and `https`. Tube-TLDR builds
  `GenericProxyConfig(http_url=..., https_url=...)` from these two keys, and
  YouTube traffic is HTTPS — leaving `https` empty defeats the purpose.
- `socks5h://` (note the `h`) resolves DNS **through** the proxy. Use it for
  residential endpoints; plain `socks5://` resolves locally and can leak or
  fail.
- Any HTTP or SOCKS5 residential endpoint works. Rotating residential pools
  (e.g. Webshare rotating residential, or any provider that gives you a
  `host:port` + credentials) are the usual choice.
- `enabled: true` with no URLs is a configuration error: the CLI exits with
  code `1` and the message *"Proxy is enabled in config.yml, but no proxy URLs
  are configured."*

### On a home connection

If you run Tube-TLDR on your own machine on a normal residential ISP, **no
proxy is needed** — leave `proxy.enabled: false`. This is the dev-machine
default.

---

## 2. Deployment options

| Option | Weight | Best for | Notes |
|--------|--------|----------|-------|
| **venv + cron** | lightest | a single VPS, one nightly job | fewest moving parts; no log rotation or failure hooks by default |
| **systemd service + timer** | light | a single VPS, one nightly job | **preferred over cron** — journald logs, `OnFailure` unit, `systemctl` control |
| **Docker + cron** | medium | you already run containers | the image's `ENTRYPOINT` is the Streamlit UI, so nightly jobs must invoke the CLI explicitly inside the container |

### 2a. venv + cron

```bash
git clone <repo> /opt/tube-tldr
cd /opt/tube-tldr
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```

Crontab (`crontab -e`), nightly at 03:15:

```cron
15 3 * * * cd /opt/tube-tldr && .venv/bin/python -m src.cli "https://www.youtube.com/watch?v=VIDEO_ID" --style entire --out /var/lib/tube-tldr/out.md >> /var/log/tube-tldr.log 2>&1
```

### 2b. systemd service + timer (preferred)

`/etc/systemd/system/tube-tldr.service`:

```ini
[Unit]
Description=Tube-TLDR nightly summarizer
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/tube-tldr
EnvironmentFile=/opt/tube-tldr/.env
ExecStart=/opt/tube-tldr/.venv/bin/python -m src.cli "https://www.youtube.com/watch?v=VIDEO_ID" --style entire --out /var/lib/tube-tldr/out.md
# Optional: ping a dead-man's switch on failure (see section 4)
OnFailure=tube-tldr-notify@%n.service
```

`/etc/systemd/system/tube-tldr.timer`:

```ini
[Unit]
Description=Run Tube-TLDR nightly

[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tube-tldr.timer
systemctl list-timers tube-tldr.timer
journalctl -u tube-tldr.service -n 50 --no-pager
```

`Persistent=true` means a missed run (VPS asleep/rebooting) fires once on the
next boot.

> **Playlist URLs are not supported yet.** `src.cli` takes a single video URL.
> Passing a playlist URL will not expand into per-video summaries — that is a
> known limitation and a nightly playlist watcher is on the roadmap. For now,
> feed it one video URL per run (or loop over a list in your own wrapper).

### 2c. Docker + cron

The image builds and runs, but its `ENTRYPOINT` is the Streamlit UI. For a
nightly job, override the entrypoint and call the CLI:

```bash
docker build -t tube-tldr:latest .

docker run --rm \
  --env-file /opt/tube-tldr/.env \
  -v /opt/tube-tldr/config.yml:/app/config.yml:ro \
  -v /var/lib/tube-tldr:/out \
  --entrypoint python \
  tube-tldr:latest \
  -m src.cli "https://www.youtube.com/watch?v=VIDEO_ID" --style entire --out /out/out.md
```

Wrap that `docker run` in a cron entry or a systemd timer exactly as above.

---

## 3. Environment & secrets

Copy `.env.example` to `.env` and fill in what you use:

| Key | Required when | Notes |
|-----|---------------|-------|
| `OLLAMA_API_KEY` | `llm.provider: ollama` **and** a cloud `base_url` | Ollama Cloud (https://ollama.com) with a paid account |
| `OPENAI_API_KEY` | `llm.provider: openai` | `API_KEY` is also accepted |

- **Local Ollama needs no key.** Point `llm.base_url` at
  `http://localhost:11434` and leave the key empty — the CLI treats a local
  Ollama endpoint as configured.
- **`llm.think`** (config.yml): thinking/reasoning models burn the
  `num_predict` budget on internal reasoning before emitting visible content,
  which can yield **empty summaries**. Leave `think: false` for summarization
  unless you know your model needs it.
- Keep `.env` out of version control (it is gitignored) and readable only by
  the service user: `chmod 600 /opt/tube-tldr/.env`.

---

## 4. Monitoring

Tube-TLDR has **no built-in alerting** — wire it up externally.

**Dead-man's switch (healthchecks.io).** Ping a check URL on success; if the
ping stops arriving, healthchecks.io alerts you:

```bash
# append to the end of the job, only on success
curl -fsS -m 10 --retry 3 https://hc-ping.com/<your-uuid> > /dev/null
```

With systemd, put the ping in an `ExecStartPost=` line, or use a wrapper
script. On failure, `OnFailure=` can hit a second unit that pings
`https://hc-ping.com/<your-uuid>/fail`.

**Push notification (ntfy.sh).** One-liner on completion:

```bash
curl -d "Tube-TLDR done" ntfy.sh/your-topic
```

Subscribe to the same topic in the ntfy app. Again: this is an external
pattern, not a Tube-TLDR feature.

---

## 5. Updating

```bash
cd /opt/tube-tldr
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q      # quick gate
sudo systemctl restart tube-tldr.timer    # or: systemctl daemon-reload if units changed
```

If you run the Docker path, rebuild the image (`docker build -t tube-tldr:latest .`)
and re-run the container.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Empty transcript / no subtitles found | YouTube blocked the datacenter IP | Configure a residential proxy (section 1) and set `proxy.enabled: true` |
| `429` or bot-check page on fetch | Same — datacenter IP | Residential proxy |
| `PoTokenRequired` / transcript API error | YouTube requires a proof-of-origin token for this client/IP | Residential proxy usually resolves it; retry later if it is transient |
| `--style chapters` / `--style shorts` fails | Video has no chapter markers in its description | Use `--style entire` (or `one-sentence`) as a fallback |
| Job hangs / times out | Long video or slow network | MCP: raise `TUBE_TLDR_TOOL_TIMEOUT_S` (default `900`). CLI: raise `--timeout` (default `900`, `<=0` disables) |
| Exit code `1` | Config problem (proxy enabled but unset, or LLM unconfigured) | Check `config.yml` and `.env` |
| Exit code `3` | Fetch failure (network, no transcript, shorts without chapters) | Check proxy and video URL |
| Exit code `4` | Summarization failure (LLM error) | Check API key, model name, and provider reachability |

Exit codes: `0` success, `1` config/IO error, `2` usage error or timeout,
`3` fetch failure, `4` summarization failure.
