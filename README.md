# FRA Sesh

```
--------------------------------
  FRA Sesh -- The Feather Research Agent Console
  Built on Odysseus
--------------------------------
```

A private AI workspace for the FRA (Feather Research Agent) system. FRA Sesh is the interface through which you converse with AI models running on your own hardware or through any API provider you choose. It is not a commercial product, not a ChatGPT competitor, and not a cloud service. It is the console of the FRA system -- your own AI workspace, under your own control.

**This is not competing with ChatGPT, Claude, or any commercial AI service.** FRA Sesh doesn't lock you into any one AI provider. You choose the engine: DeepSeek, Claude, any OpenAI-compatible API, or models running locally on your computer. The intelligence comes from the model you connect. FRA Sesh is the workspace.

## What FRA Sesh Is

FRA Sesh is the front-end workspace of the **Feather Research Agent (FRA)** system -- a private, self-hosted AI console. The FRA system also includes FRA Rekh, the autonomous research agent (built on Agent Zero). Together they form a complete private AI research environment.

**Key principle:** FRA Sesh is an interface, not an AI. It doesn't compete with anyone's AI. It lets you use any AI model through one consistent workspace that you own and control.

## Features

- **Chat** -- converse with DeepSeek, Claude, OpenAI, Ollama, vLLM, llama.cpp, or any OpenAI-compatible API. Add new models in seconds from Settings
- **Agent** -- hand tools to the AI and let it run tasks autonomously. Built on opencode with MCP, web, files, shell, skills, and persistent memory
- **Cookbook** -- scans your hardware, recommends models, one-click download and serve with VRAM-aware fit scoring
- **Deep Research** -- multi-step research that gathers, reads, and synthesizes sources into visual reports
- **Compare** -- test models side by side with blind comparison. No bias
- **Documents** -- multi-tab editor for markdown, HTML, CSV with syntax highlighting and AI-assisted editing
- **Memory / Skills** -- persistent knowledge base that grows with use. ChromaDB + fastembed with vector and keyword retrieval
- **Email** -- IMAP/SMTP inbox with AI triage: urgency, auto-tag, auto-summary, auto-reply drafts
- **Notes & Tasks** -- notes with reminders, todo lists, and scheduled agent tasks
- **Calendar** -- local-first with CalDAV sync to Radicale, Nextcloud, Apple, Fastmail
- **Mobile** -- responsive design, installable as PWA, works on phone and desktop

## Built On

FRA Sesh is built on **[Odysseus](https://github.com/pewdiepie-archdaemon/odysseus)** -- an open-source, MIT-licensed AI workspace created by pewdiepie-archdaemon. Full credit and gratitude to the Odysseus project. FRA Sesh is a renamed and customized instance of Odysseus, integrated into the Feather Research Agent system.

## Quick Start

Defaults work out of the box: clone, run, then configure models inside **Settings**.

On first setup, FRA Sesh creates an admin account and prints a temporary password in the terminal. Use that for first login, then change it in Settings.

### Docker (recommended)

```bash
git clone https://github.com/pewdiepie-archdaemon/odysseus.git
cd odysseus
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:7000`.

### Native Windows

```powershell
git clone https://github.com/pewdiepie-archdaemon/odysseus.git
cd odysseus
py -3.11 -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python setup.py
python -m uvicorn app:app --host 127.0.0.1 --port 7000
```

### Native Linux / macOS

```bash
git clone https://github.com/pewdiepie-archdaemon/odysseus.git
cd odysseus
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py
python -m uvicorn app:app --host 127.0.0.1 --port 7000
```

## Model Providers (You Choose)

FRA Sesh doesn't force any AI provider. Add any of these in Settings:

- **DeepSeek** -- add via OpenRouter or direct API
- **Claude** -- via Anthropic API
- **OpenAI** -- GPT-4o, o1, o3, etc.
- **Ollama** -- any local model (Llama, Mistral, Gemma, etc.)
- **vLLM / llama.cpp** -- self-hosted models with GPU acceleration
- **OpenRouter** -- unified access to 200+ models
- **GitHub Copilot** -- via token

The workspace is yours. You decide which intelligence sits behind it.

## Architecture

```
app.py                   # FastAPI entry point
core/      auth, database, middleware, constants
src/       llm_core, agent_loop, agent_tools, chat_processor, search
routes/    chat, session, document, memory, model endpoints
services/  docs, memory, search, cookbook
static/    index.html + app.js + style.css (modular front-end)
```

## Security

FRA Sesh is a self-hosted admin console. Keep `AUTH_ENABLED=true` for any network deployment. Do not expose directly to the public internet. All user data lives in `data/` (gitignored): databases, memory, uploads, settings, API keys.

## License

MIT -- see [LICENSE](LICENSE). Built on Odysseus, also MIT-licensed.

---

**FRA Sesh** -- the Feather Research Agent Console. Part of the FRA system alongside FRA Rekh.

*Maat is the measure.*
