---
name: opencode-kiro-gateway
description: >
  Install OpenCode and configure Kiro Gateway on macOS for using Kiro models
  without any OpenCode plugin. Use when the user wants to set up OpenCode with
  Kiro Gateway, install OpenCode, configure kiro-gateway proxy, or connect
  OpenCode to Kiro models. Triggers on "install opencode", "setup kiro gateway",
  "configure opencode with kiro", "opencode kiro setup", or any request to get
  OpenCode working with Kiro API through the gateway proxy.
---

# OpenCode + Kiro Gateway Setup Skill

Set up OpenCode with Kiro Gateway on macOS. No OpenCode plugin needed — all
requests go through a local kiro-gateway proxy.

## Prerequisites

- macOS
- Kiro IDE installed and logged in (credentials at `~/.aws/sso/cache/kiro-auth-token.json`)
- Python 3.10+
- Git

## Quick Setup (Automated)

Run the bundled script for a one-command setup:

```bash
bash scripts/setup_opencode_kiro.sh
```

Options:

```
--proxy-key KEY    Gateway proxy password (default: sk-kiro-gateway)
--port PORT        Gateway listen port (default: 8000)
--vpn-proxy URL    VPN/proxy URL for restricted networks
```

The script handles:
1. Install OpenCode (via Homebrew > npm > curl fallback)
2. Clone and install kiro-gateway + Python dependencies
3. Write gateway `.env` config
4. Write OpenCode `opencode.json` with kiro-gateway provider

## Manual Setup

If the automated script is not suitable, follow these steps:

### 1. Install OpenCode

```bash
# Homebrew (recommended on macOS)
brew install anomalyco/tap/opencode

# Or npm
npm install -g opencode-ai

# Or install script
curl -fsSL https://opencode.ai/install | bash
```

### 2. Clone kiro-gateway

```bash
git clone https://github.com/jwadow/kiro-gateway.git ~/kiro-gateway
cd ~/kiro-gateway
pip install -r requirements.txt
```

### 3. Configure gateway `.env`

Create `~/kiro-gateway/.env`:

```env
PROXY_API_KEY="sk-kiro-gateway"
KIRO_CREDS_FILE="~/.aws/sso/cache/kiro-auth-token.json"
```

### 4. Configure OpenCode

Write `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "kiro-gateway": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Kiro Gateway",
      "options": {
        "baseURL": "http://localhost:8000/v1",
        "apiKey": "sk-kiro-gateway"
      },
      "models": {
        "auto-kiro": {
          "name": "[GW] Auto (Kiro)",
          "limit": { "context": 200000, "output": 64000 }
        },
        "claude-sonnet-4.6": {
          "name": "[GW] Claude Sonnet 4.6",
          "limit": { "context": 200000, "output": 64000 }
        },
        "claude-sonnet-4.5": {
          "name": "[GW] Claude Sonnet 4.5",
          "limit": { "context": 200000, "output": 64000 }
        },
        "claude-opus-4.6": {
          "name": "[GW] Claude Opus 4.6",
          "limit": { "context": 200000, "output": 64000 }
        },
        "claude-haiku-4.5": {
          "name": "[GW] Claude Haiku 4.5",
          "limit": { "context": 200000, "output": 64000 }
        }
      }
    }
  }
}
```

`options.apiKey` must match `PROXY_API_KEY` in `.env`.

### 5. Start and verify

```bash
# Terminal 1: start gateway
cd ~/kiro-gateway && python main.py

# Terminal 2: verify
curl http://localhost:8000/health

# Terminal 2: run opencode, then /models to pick a [GW] model
opencode
```

## Verification Checklist

After setup, confirm:

- [ ] `opencode --version` returns a version
- [ ] `~/.aws/sso/cache/kiro-auth-token.json` exists
- [ ] `curl http://localhost:8000/health` returns `{"status":"healthy",...}`
- [ ] In OpenCode, `/models` shows `[GW]` prefixed models
- [ ] Sending a test message gets a response

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `opencode: command not found` | Re-run install or add to PATH |
| Gateway health check fails | Ensure `python main.py` is running |
| Auth error / token expired | Re-login Kiro IDE, check credentials file exists |
| Connection refused in OpenCode | Verify `baseURL` port matches gateway port |
| Empty response / timeout | Check network; add `VPN_PROXY_URL` in `.env` if behind firewall |
