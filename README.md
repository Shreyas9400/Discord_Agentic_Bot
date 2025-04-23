# Discord Parallel Researcher Bot

A Discord bot for parallel web research, in-depth reporting, and context-aware chat, powered by SearXNG, Qdrant, Mem0, and Google Gemini.

## Demo



https://github.com/user-attachments/assets/4e92cde1-a9bb-4e99-ade8-23c15e09b218



## Features

- Parallel web search using SearXNG (self-hosted metasearch engine)
- In-depth research reports with Gemini LLM
- Memory system with Qdrant and Mem0 for context-aware conversations
- Discord command interface for research, search, chat, and knowledge base queries

## Requirements

- Docker & Docker Compose
- Python 3.10+ (for development outside Docker)
- Discord Bot Token
- Google API Key (for Gemini)
- SearXNG and Qdrant (run via Docker Compose)

## Setup

### 1. Clone the repository

```sh
git clone https://github.com/Shreyas9400/Discord_Agentic_Bot.git
cd Discord_Agentic_Bot
```

### 2. Configure environment variables

Create a `.env` file (do **not** commit this file):

```
DISCORD_TOKEN=your_discord_token_here
SEARXNG_SECRET_KEY=your_searxng_secret_key_here  # Any random long string, used for SearXNG security
GOOGLE_API_KEY=your_google_api_key_here
```

#### How to set up your Discord Bot Token

**STEP 1: Create a Bot on Discord Developer Portal**  
Go to: https://discord.com/developers/applications

- Click on **"New Application"**
- Name your application (e.g., MyFirstBot) and click **Create**

**STEP 2: Add a Bot to Your Application**  
- In the application menu (left sidebar), go to **“Bot”**
- Click **“Add Bot”** → Yes, do it!
- Optionally:
  - Change the bot’s username
  - Upload a bot avatar
  - Enable **MESSAGE CONTENT INTENT** if your bot needs to read message content

**STEP 3: Copy Your Bot Token**  
- Under the **Bot** tab, click **“Reset Token”** to generate a token
- Copy the token – it’s like a password. Keep it secret and store it safely (you'll use it in your code)

**STEP 4: Set Bot Permissions (Scopes & Privileges)**  
- Go to **OAuth2 → URL Generator**
- Select the following under **Scopes**:
  - `bot`
  - (optionally) `applications.commands` if you’re using slash commands
- Under **Bot Permissions**, choose what your bot should be able to do:
  - E.g., Send Messages, Read Message History, Embed Links, etc.
- Copy the generated URL from the bottom of the page

**STEP 5: Invite the Bot to Your Server**  
- Paste the copied URL into your browser
- Select your server (you must have Manage Server permissions)
- Click **Authorize**

### 3. Build and run with Docker Compose

```sh
docker compose up --build
```

- This will start SearXNG, Qdrant, and the Discord bot.
- The bot will connect to Discord and be ready to use.

## Usage

In your Discord server, use the following commands:

- `!ask [query]` — Smart query handler (auto-selects best agent)
- `!force_search [query]` — Force web search
- `!force_research [topic]` — Force in-depth research report
- `!force_knowledge [query]` — Force knowledge base answer
- `!direct_chat` — Enable direct chat mode in the channel
- `!memory_status` — Show memory system status
- `!clear_memory` — Clear your conversation memory
- `!bot_help` — Show help

## File Structure

- `discord_bot.py` — Main Discord bot logic
- `parallel_research_agent.py` — Parallel research agent logic
- `web_search_agent.py` — Web search agent logic
- `searxng_client.py` — SearXNG API client
- `Memory.py` — Memory system integration (Qdrant/Mem0)
- `shared_utils.py` — Shared context utilities
- `settings.yml` — SearXNG configuration (mounted into the container)
- `requirements.txt` — Python dependencies
- `docker-compose.yml` — Multi-service Docker Compose setup
- `.env` — Environment variables (not committed)

## Security

- **Never commit secrets** (Discord tokens, API keys, secret keys) to your repository.
- All secrets should be stored in `.env` and loaded via environment variables.

## Troubleshooting

- If SearXNG returns 403 errors, ensure `settings.yml` is mounted and allows the `json` format.
- If secrets are detected by GitHub, remove them from your repo history and use environment variables.

## License

MIT License

---

**Contributions welcome!**
