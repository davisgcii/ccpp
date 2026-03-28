#!/bin/bash
#
# CC++ PII Masking — Setup
#
# Installs everything needed to run CC++ on a fresh macOS machine:
#   Homebrew, uv, Python dependencies, .env configuration
#
# Usage: ./setup.sh [--no-prompt]
#
# Options:
#   --no-prompt    Skip interactive prompts (API key, Ollama install)
#   -h, --help     Show this help message
#

set -e

# ── Flags ─────────────────────────────────────────────────────────

NO_PROMPT=false
for arg in "$@"; do
    case "$arg" in
        --no-prompt) NO_PROMPT=true ;;
        -h|--help)
            echo "CC++ PII Masking — Setup"
            echo ""
            echo "Usage: ./setup.sh [--no-prompt]"
            echo ""
            echo "Options:"
            echo "  --no-prompt    Skip interactive prompts (API key, Ollama install)"
            echo "  -h, --help     Show this help message"
            exit 0 ;;
    esac
done

# ── Colors ────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

print_step()    { echo -e "\n${BLUE}==>${NC} ${BOLD}${1}${NC}"; }
print_success() { echo -e "  ${GREEN}✓${NC} ${1}"; }
print_warning() { echo -e "  ${YELLOW}!${NC} ${1}"; }
print_error()   { echo -e "  ${RED}✗${NC} ${1}"; }

# ── Pre-flight ────────────────────────────────────────────────────

check_macos() {
    if [[ "$(uname)" != "Darwin" ]]; then
        print_warning "This script is optimized for macOS (Apple Silicon)."
        print_warning "MLX backend requires Apple Silicon. Use Ollama for other platforms."
        if [[ "$NO_PROMPT" == true ]]; then return; fi
        read -p "  Continue anyway? (y/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || exit 1
    fi
}

# ── Homebrew ──────────────────────────────────────────────────────

install_homebrew() {
    print_step "Homebrew"
    if command -v brew &> /dev/null; then
        print_success "Already installed"
    else
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        [[ -f "/opt/homebrew/bin/brew" ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
        print_success "Installed"
    fi
}

# ── uv ────────────────────────────────────────────────────────────

install_uv() {
    print_step "uv (Python package manager)"
    if command -v uv &> /dev/null; then
        print_success "Already installed ($(uv --version))"
    else
        brew install uv
        print_success "Installed"
    fi
}

# ── Python dependencies ──────────────────────────────────────────

install_deps() {
    print_step "Python dependencies"
    uv sync --extra dev
    print_success "All dependencies installed (main + dev)"
}

# ── .env / API keys ──────────────────────────────────────────────

setup_env() {
    print_step "API keys"

    # Already configured — skip
    if [[ -f ".env" ]] && grep -q '^ANTHROPIC_API_KEY=sk-ant-' .env; then
        print_success "Anthropic API key configured"
        return
    fi

    # Non-interactive mode — just ensure .env exists
    if [[ "$NO_PROMPT" == true ]]; then
        [[ ! -f ".env" ]] && cp .env.example .env 2>/dev/null || true
        print_warning "No API key — add ANTHROPIC_API_KEY to .env for data generation"
        return
    fi

    echo
    echo -e "  ${DIM}The default backend (MLX) runs entirely locally — no API key needed.${NC}"
    echo -e "  ${DIM}An Anthropic key is only required for synthetic data generation${NC}"
    echo -e "  ${DIM}and cloud API backends.${NC}"
    echo
    echo "  Get one at: https://console.anthropic.com/settings/keys"
    echo
    read -p "  Paste your ANTHROPIC_API_KEY (or Enter to skip): " api_key

    if [[ -n "$api_key" ]]; then
        cat > .env <<EOL
# API keys
ANTHROPIC_API_KEY=${api_key}
# OPENAI_API_KEY=sk-your-key-here
# OLLAMA_HOST=http://localhost:11434
EOL
        print_success "API key saved to .env"
    else
        [[ ! -f ".env" ]] && cp .env.example .env 2>/dev/null || true
        print_warning "Skipped — you can add it to .env later"
    fi
}

# ── Ollama (optional) ────────────────────────────────────────────

setup_ollama() {
    print_step "Ollama (optional cross-platform backend)"

    if command -v ollama &> /dev/null; then
        print_success "Already installed"
        return
    fi

    if [[ "$NO_PROMPT" == true ]]; then
        print_warning "Not installed — install later with: brew install ollama"
        return
    fi

    echo -e "  ${DIM}Ollama is an alternative to MLX for running local models.${NC}"
    echo -e "  ${DIM}Not required if using the default MLX backend on Apple Silicon.${NC}"
    echo
    read -p "  Install Ollama via Homebrew? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install ollama
        print_success "Installed — start with: ollama serve"
    else
        print_warning "Skipped — install later with: brew install ollama"
    fi
}

# ── Verify ────────────────────────────────────────────────────────

verify() {
    print_step "Verifying installation"

    if uv run python -c "from ccpp.config import load_config; load_config()" &> /dev/null; then
        print_success "Config system OK"
    else
        print_error "Config failed to load — check configs/default.yaml"
    fi

    if [[ "$(uname -m)" == "arm64" ]]; then
        if uv run python -c "from ccpp.llm.mlx_backend import MLXBackend" &> /dev/null; then
            print_success "MLX backend OK"
        else
            print_warning "MLX backend import failed"
        fi
    fi
}

# ── Done ──────────────────────────────────────────────────────────

print_done() {
    local has_key=false
    local has_ollama=false
    [[ -f ".env" ]] && grep -q '^ANTHROPIC_API_KEY=sk-ant-' .env && has_key=true
    command -v ollama &> /dev/null && has_ollama=true

    echo
    echo -e "  ${GREEN}┌──────────────────────────────────────────┐${NC}"
    echo -e "  ${GREEN}│${NC}            ${BOLD}Setup complete!${NC}               ${GREEN}│${NC}"
    echo -e "  ${GREEN}└──────────────────────────────────────────┘${NC}"
    echo
    echo -e "  ${BOLD}Start the GUI:${NC}"
    echo "    uv run python scripts/gui_client.py"
    echo -e "    ${DIM}→ opens at http://127.0.0.1:7860${NC}"
    echo
    echo -e "  ${BOLD}Run tests:${NC}"
    echo "    uv run pytest"
    echo
    echo -e "  ${BOLD}Status:${NC}"
    echo -e "    Backend:        ${BOLD}MLX${NC} (Apple Silicon, local)"

    if [[ "$has_key" == true ]]; then
        echo -e "    Anthropic key:  ${GREEN}configured${NC}"
    else
        echo -e "    Anthropic key:  ${YELLOW}not set${NC} ${DIM}(optional for local use)${NC}"
    fi

    if [[ "$has_ollama" == true ]]; then
        echo -e "    Ollama:         ${GREEN}installed${NC}"
    else
        echo -e "    Ollama:         ${DIM}not installed (optional)${NC}"
    fi

    echo
    echo -e "  ${DIM}Note: Base models (~2 GB) download automatically on first launch.${NC}"
    echo -e "  ${DIM}Logs: /tmp/gui_debug.log · /tmp/prompt_logs.jsonl${NC}"
    echo
}

# ── Main ──────────────────────────────────────────────────────────

main() {
    echo -e "${BLUE}"
    echo "  ██████╗ ██████╗ ██████╗ ██████╗ "
    echo " ██╔════╝██╔════╝ ██╔══██╗██╔══██╗"
    echo " ██║     ██║      ██████╔╝██████╔╝"
    echo " ██║     ██║      ██╔═══╝ ██╔═══╝ "
    echo " ╚██████╗╚██████╗ ██║     ██║     "
    echo "  ╚═════╝ ╚═════╝ ╚═╝     ╚═╝    "
    echo -e "${NC}"
    echo -e " ${BOLD}Streaming PII Detection & Masking${NC}"
    echo -e " ${DIM}────────────────────────────────────${NC}"
    echo

    if [[ ! -f "pyproject.toml" ]]; then
        print_error "pyproject.toml not found. Run this script from the ccpp root directory."
        exit 1
    fi

    check_macos
    install_homebrew
    install_uv
    install_deps
    setup_env
    setup_ollama
    verify
    print_done
}

main "$@"
