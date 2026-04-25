#!/usr/bin/env bash
# setup_opencode_kiro.sh — Install OpenCode + Kiro Gateway on macOS
# Usage: bash setup_opencode_kiro.sh [--proxy-key KEY] [--port PORT] [--vpn-proxy URL]
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────
PROXY_API_KEY="sk-kiro-gateway"
GATEWAY_PORT="8000"
VPN_PROXY_URL=""
KIRO_CREDS_FILE="$HOME/.aws/sso/cache/kiro-auth-token.json"
GATEWAY_DIR="$HOME/kiro-gateway"
OPENCODE_CONFIG_DIR="$HOME/.config/opencode"
OPENCODE_CONFIG="$OPENCODE_CONFIG_DIR/opencode.json"

# ── Parse args ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --proxy-key)  PROXY_API_KEY="$2"; shift 2 ;;
    --port)       GATEWAY_PORT="$2"; shift 2 ;;
    --vpn-proxy)  VPN_PROXY_URL="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [--proxy-key KEY] [--port PORT] [--vpn-proxy URL]"
      echo "  --proxy-key  Gateway proxy password (default: sk-kiro-gateway)"
      echo "  --port       Gateway listen port (default: 8000)"
      echo "  --vpn-proxy  VPN/proxy URL for restricted networks"
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

info()  { printf "\033[1;34m[INFO]\033[0m  %s\n" "$1"; }
ok()    { printf "\033[1;32m[OK]\033[0m    %s\n" "$1"; }
warn()  { printf "\033[1;33m[WARN]\033[0m  %s\n" "$1"; }
fail()  { printf "\033[1;31m[FAIL]\033[0m  %s\n" "$1"; exit 1; }

# ── Pre-flight checks ────────────────────────────────────────────────
[[ "$(uname -s)" == "Darwin" ]] || fail "This script is for macOS only."

info "Checking prerequisites..."

# Check Kiro IDE credentials
if [[ ! -f "$KIRO_CREDS_FILE" ]]; then
  fail "Kiro credentials not found at $KIRO_CREDS_FILE
  Please install Kiro IDE (https://kiro.dev/) and log in first."
fi
ok "Kiro credentials found: $KIRO_CREDS_FILE"

# ── Step 1: Install OpenCode ─────────────────────────────────────────
info "Step 1/4: Installing OpenCode..."

if command -v opencode &>/dev/null; then
  ok "OpenCode already installed: $(opencode --version 2>/dev/null || echo 'unknown version')"
else
  if command -v brew &>/dev/null; then
    info "Installing via Homebrew..."
    brew install anomalyco/tap/opencode
  elif command -v npm &>/dev/null; then
    info "Installing via npm..."
    npm install -g opencode-ai
  elif command -v curl &>/dev/null; then
    info "Installing via install script..."
    curl -fsSL https://opencode.ai/install | bash
  else
    fail "No package manager found. Install Homebrew, Node.js, or curl first."
  fi

  # Verify
  if command -v opencode &>/dev/null; then
    ok "OpenCode installed successfully."
  else
    fail "OpenCode installation failed. Try manually: brew install anomalyco/tap/opencode"
  fi
fi

# ── Step 2: Clone & setup kiro-gateway ────────────────────────────────
info "Step 2/4: Setting up kiro-gateway..."

if [[ -d "$GATEWAY_DIR" ]]; then
  info "kiro-gateway directory exists, pulling latest..."
  git -C "$GATEWAY_DIR" pull --ff-only 2>/dev/null || warn "git pull failed, using existing version."
else
  info "Cloning kiro-gateway..."
  git clone https://github.com/jwadow/kiro-gateway.git "$GATEWAY_DIR"
fi

# Find Python 3.10+ — detect all candidates including virtual environments
declare -a PYTHON_CANDIDATES=()
declare -a PYTHON_LABELS=()

# Helper: check if a python binary meets version requirement
check_python() {
  local bin="$1"
  if [[ ! -x "$bin" ]] && ! command -v "$bin" &>/dev/null; then
    return 1
  fi
  local ver
  ver=$("$bin" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
  local major="${ver%%.*}"
  local minor="${ver#*.}"
  [[ "$major" -ge 3 ]] && [[ "$minor" -ge 10 ]]
}

# 1) pyenv virtualenvs
if command -v pyenv &>/dev/null; then
  while IFS= read -r venv_name; do
    [[ -z "$venv_name" ]] && continue
    bin="$(pyenv prefix "$venv_name" 2>/dev/null)/bin/python"
    if [[ -x "$bin" ]] && check_python "$bin"; then
      ver=$("$bin" --version 2>/dev/null)
      PYTHON_CANDIDATES+=("$bin")
      PYTHON_LABELS+=("pyenv: $venv_name ($ver)")
    fi
  done < <(pyenv virtualenvs --bare 2>/dev/null)
fi

# 2) conda envs
if command -v conda &>/dev/null; then
  while IFS= read -r env_path; do
    [[ -z "$env_path" ]] && continue
    bin="$env_path/bin/python"
    if [[ -x "$bin" ]] && check_python "$bin"; then
      ver=$("$bin" --version 2>/dev/null)
      env_name=$(basename "$env_path")
      PYTHON_CANDIDATES+=("$bin")
      PYTHON_LABELS+=("conda: $env_name ($ver)")
    fi
  done < <(conda info --envs 2>/dev/null | grep -v '^#' | awk '{print $NF}' | grep -v '^$')
fi

# 3) System python3 / python
for candidate in python3 python; do
  if command -v "$candidate" &>/dev/null && check_python "$candidate"; then
    bin="$(command -v "$candidate")"
    ver=$("$bin" --version 2>/dev/null)
    PYTHON_CANDIDATES+=("$bin")
    PYTHON_LABELS+=("system: $candidate ($ver)")
  fi
done

# No valid Python found — exit with guidance
if [[ ${#PYTHON_CANDIDATES[@]} -eq 0 ]]; then
  fail "Python 3.10+ not found on this system.
  Please install Python 3.10+ manually before running this script.
  Options:
    brew install python@3.12
    pyenv install 3.12.8
    Download from https://www.python.org/downloads/"
fi

# Single candidate — use it directly
if [[ ${#PYTHON_CANDIDATES[@]} -eq 1 ]]; then
  PYTHON="${PYTHON_CANDIDATES[0]}"
  ok "Using Python: ${PYTHON_LABELS[0]}"
else
  # Multiple candidates — let user choose
  echo ""
  info "Found multiple Python environments (3.10+):"
  echo ""
  for i in "${!PYTHON_LABELS[@]}"; do
    printf "  \033[1;36m[%d]\033[0m  %s\n" "$((i+1))" "${PYTHON_LABELS[$i]}"
  done
  echo ""
  printf "  Select [1-%d]: " "${#PYTHON_CANDIDATES[@]}"
  read -r choice

  # Validate input
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [[ "$choice" -lt 1 ]] || [[ "$choice" -gt ${#PYTHON_CANDIDATES[@]} ]]; then
    fail "Invalid selection. Please re-run and pick a number between 1 and ${#PYTHON_CANDIDATES[@]}."
  fi

  PYTHON="${PYTHON_CANDIDATES[$((choice-1))]}"
  ok "Using Python: ${PYTHON_LABELS[$((choice-1))]}"
fi

# Install dependencies
info "Installing Python dependencies..."
$PYTHON -m pip install -r "$GATEWAY_DIR/requirements.txt" --quiet 2>/dev/null || \
  $PYTHON -m pip install -r "$GATEWAY_DIR/requirements.txt"
ok "Python dependencies installed."

# ── Step 3: Configure kiro-gateway .env ───────────────────────────────
info "Step 3/4: Configuring kiro-gateway..."

ENV_FILE="$GATEWAY_DIR/.env"

# Helper: set a key in .env (update if exists, append if not)
set_env_var() {
  local key="$1" value="$2" file="$3"
  if [[ -f "$file" ]] && grep -q "^${key}=" "$file"; then
    # Update existing key (macOS sed -i requires '')
    sed -i '' "s|^${key}=.*|${key}=\"${value}\"|" "$file"
  else
    echo "${key}=\"${value}\"" >> "$file"
  fi
}

# Create .env from .env.example if it doesn't exist
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$GATEWAY_DIR/.env.example" ]]; then
    cp "$GATEWAY_DIR/.env.example" "$ENV_FILE"
    info "Created .env from .env.example"
  else
    touch "$ENV_FILE"
  fi
fi

# Merge required keys (preserves all other existing settings)
set_env_var "PROXY_API_KEY" "$PROXY_API_KEY" "$ENV_FILE"
set_env_var "KIRO_CREDS_FILE" "$KIRO_CREDS_FILE" "$ENV_FILE"

if [[ -n "$VPN_PROXY_URL" ]]; then
  set_env_var "VPN_PROXY_URL" "$VPN_PROXY_URL" "$ENV_FILE"
fi

if [[ "$GATEWAY_PORT" != "8000" ]]; then
  set_env_var "SERVER_PORT" "$GATEWAY_PORT" "$ENV_FILE"
fi

ok "Gateway .env configured (merged): $ENV_FILE"

# ── Step 4: Configure OpenCode ────────────────────────────────────────
info "Step 4/4: Configuring OpenCode..."

mkdir -p "$OPENCODE_CONFIG_DIR"

# kiro-gateway provider JSON fragment
PROVIDER_FRAGMENT=$(cat <<JSONEOF
{
  "npm": "@ai-sdk/openai-compatible",
  "name": "Kiro Gateway",
  "options": {
    "baseURL": "http://localhost:${GATEWAY_PORT}/v1",
    "apiKey": "${PROXY_API_KEY}"
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
    "claude-sonnet-4": {
      "name": "[GW] Claude Sonnet 4",
      "limit": { "context": 200000, "output": 64000 }
    },
    "claude-opus-4.6": {
      "name": "[GW] Claude Opus 4.6",
      "limit": { "context": 200000, "output": 64000 }
    },
    "claude-opus-4.5": {
      "name": "[GW] Claude Opus 4.5",
      "limit": { "context": 200000, "output": 64000 }
    },
    "claude-haiku-4.5": {
      "name": "[GW] Claude Haiku 4.5",
      "limit": { "context": 200000, "output": 64000 }
    },
    "claude-3.7-sonnet": {
      "name": "[GW] Claude 3.7 Sonnet",
      "limit": { "context": 200000, "output": 64000 }
    }
  }
}
JSONEOF
)

if [[ -f "$OPENCODE_CONFIG" ]]; then
  # Merge: inject kiro-gateway provider into existing config using Python
  info "Existing OpenCode config found, merging kiro-gateway provider..."
  BACKUP="${OPENCODE_CONFIG}.bak.$(date +%s)"
  cp "$OPENCODE_CONFIG" "$BACKUP"

  $PYTHON -c "
import json, sys

config_path = sys.argv[1]
fragment = json.loads(sys.argv[2])

with open(config_path, 'r') as f:
    config = json.load(f)

config.setdefault('\$schema', 'https://opencode.ai/config.json')
config.setdefault('provider', {})
config['provider']['kiro-gateway'] = fragment

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
" "$OPENCODE_CONFIG" "$PROVIDER_FRAGMENT"

  ok "kiro-gateway provider merged into existing config (backup: $BACKUP)"
else
  # Fresh install: create minimal config
  cat > "$OPENCODE_CONFIG" <<CFGEOF
{
  "\$schema": "https://opencode.ai/config.json",
  "provider": {
    "kiro-gateway": $(echo "$PROVIDER_FRAGMENT")
  }
}
CFGEOF
  ok "OpenCode config created: $OPENCODE_CONFIG"
fi

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "  Gateway dir:    $GATEWAY_DIR"
echo "  Gateway port:   $GATEWAY_PORT"
echo "  Proxy key:      $PROXY_API_KEY"
echo "  OpenCode config: $OPENCODE_CONFIG"
echo ""
echo "  Next steps:"
echo "  1. Start gateway:  cd $GATEWAY_DIR && $PYTHON main.py"
echo "  2. Verify health:  curl http://localhost:$GATEWAY_PORT/health"
echo "  3. Run OpenCode:   opencode"
echo "  4. Select model:   /models -> choose [GW] prefixed model"
echo ""
