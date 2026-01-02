# discord-support-agent

[![ci](https://github.com/detailobsessed/discord-support-agent/workflows/ci/badge.svg)](https://github.com/detailobsessed/discord-support-agent/actions?query=workflow%3Aci)

AI agent that monitors Discord servers and notifies about support requests.

Uses local LLMs via [Ollama](https://ollama.com/) for cost-free inference.

## Prerequisites

1. **Ollama** - Install from [ollama.com](https://ollama.com/) and pull a model:

   ```bash
   ollama pull qwen3:30b  # or qwen3:8b for less RAM
   ```

2. **Discord Bot** - Create a bot at [discord.com/developers](https://discord.com/developers/applications):
   - Create a new application
   - Go to Bot → Reset Token → Copy the token
   - Enable "Message Content Intent" under Privileged Gateway Intents
   - Go to OAuth2 → URL Generator → Select `bot` scope
   - Select permissions: Read Messages/View Channels, Read Message History
   - Use the generated URL to invite the bot to your server

## Setup

```bash
# Clone and install
git clone https://github.com/detailobsessed/discord-support-agent.git
cd discord-support-agent
uv sync

# Configure
cp .env.example .env
# Edit .env and add your DISCORD_TOKEN

# Run
uv run python main.py
```

## Configuration

Environment variables (set in `.env`):

| Variable                 | Required | Default                     | Description                              |
| ------------------------ | -------- | --------------------------- | ---------------------------------------- |
| `DISCORD_TOKEN`          | Yes      | -                           | Discord bot token                        |
| `DISCORD_GUILD_IDS`      | No       | (all)                       | Comma-separated guild IDs to monitor     |
| `OLLAMA_BASE_URL`        | No       | `http://localhost:11434/v1` | Ollama API URL                           |
| `OLLAMA_MODEL`           | No       | `qwen3:30b`                 | Model for classification                 |
| `ISSUE_TRACKER`          | No       | `none`                      | Issue tracker: `none`, `github`, `linear`|
| `GITHUB_TOKEN`           | No       | -                           | GitHub PAT for issue creation            |
| `GITHUB_REPO`            | No       | -                           | GitHub repo for issues (see below)       |
| `OTEL_ENABLED`           | No       | `false`                     | Enable OpenTelemetry instrumentation     |
| `OTEL_EXPORTER_ENDPOINT` | No       | `http://localhost:4318`     | OTLP exporter endpoint                   |

### GitHub Issue Tracking

The easiest way to set up GitHub issue tracking is with the interactive setup:

```bash
uv run setup.py
```

This will:

- Check your `gh` CLI authentication
- Create a dedicated repository for support issues
- Update your `.env` file automatically

**Manual setup:**

1. Create a new repo (e.g., `yourorg/discord-support-issues`)
2. Create a [fine-grained PAT](https://github.com/settings/tokens?type=beta) with `Issues: Read and write` permission for that repo only
3. Set in `.env`:

   ```
   ISSUE_TRACKER=github
   GITHUB_TOKEN=ghp_your_token
   GITHUB_REPO=yourorg/discord-support-issues
   ```

**Why a separate repo?**

- **Security** - Bot token only has access to issues, not your source code
- **Noise reduction** - Support tickets won't clutter your project's issue tracker
- **Permissions** - Different team members can triage support vs. code issues

The bot will auto-create labels (`support`, `bug`, `complaint`, `needs-response`, `needs-triage`) on first use.

## How It Works

1. Bot connects to Discord and listens for messages in real-time
2. Each message is classified by the local LLM into categories:
   - **Support Request** - User asking for help
   - **Complaint** - User expressing frustration
   - **Bug Report** - User reporting a problem
   - **General Chat** - Normal conversation (ignored)
3. The classifier can use tools to get additional context:
   - **User context** - Is the user new? What's their activity level?
   - **Channel context** - Recent messages for conversation flow
4. Messages requiring attention trigger a macOS notification
5. Optionally, issues are created in GitHub or Linear

## Features

- **Local LLM inference** via Ollama (no API costs)
- **Smart classification** with confidence scores and automatic retries
- **Agent tools** for user/channel context during classification
- **Usage tracking** for token consumption monitoring
- **OpenTelemetry instrumentation** via Logfire (works with otel-tui, Jaeger, etc.)
- **Issue tracking** integration (GitHub Issues, Linear planned)
- **Pydantic Evals** for classifier quality testing
