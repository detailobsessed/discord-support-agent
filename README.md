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

| Variable             | Required | Default                      | Description                          |
| -------------------- | -------- | ---------------------------- | ------------------------------------ |
| `DISCORD_TOKEN`      | Yes      | -                            | Discord bot token                    |
| `DISCORD_GUILD_IDS`  | No       | (all)                        | Comma-separated guild IDs to monitor |
| `OLLAMA_BASE_URL`    | No       | `http://localhost:11434/v1`  | Ollama API URL                       |
| `OLLAMA_MODEL`       | No       | `qwen3:30b`                  | Model for classification             |

## How It Works

1. Bot connects to Discord and listens for messages in real-time
2. Each message is classified by the local LLM into categories:
   - **Support Request** - User asking for help
   - **Complaint** - User expressing frustration
   - **Bug Report** - User reporting a problem
   - **General Chat** - Normal conversation (ignored)
3. Messages requiring attention trigger a macOS notification
