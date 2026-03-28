#!/bin/bash
#
# CC++ PII Masking System - Setup Script
#
# Installs everything needed to run CC++ on a fresh macOS machine:
# - Homebrew, uv (Python package manager)
# - Python dependencies
# - Creates .env from template
# - Generates MLX training data if missing
#
# Usage: ./setup.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "\n${BLUE}==>${NC} ${1}"
}

print_success() {
    echo -e "${GREEN}✓${NC} ${1}"
}

print_warning() {
    echo -e "${YELLOW}!${NC} ${1}"
}

print_error() {
    echo -e "${RED}✗${NC} ${1}"
}

# Check if running on macOS
check_macos() {
    if [[ "$(uname)" != "Darwin" ]]; then
        print_warning "This script is optimized for macOS with Homebrew."
        print_warning "For Linux, install ollama manually: https://ollama.ai/download"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Install Homebrew if not present
install_homebrew() {
    print_step "Checking Homebrew..."
    if command -v brew &> /dev/null; then
        print_success "Homebrew is already installed"
    else
        print_step "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add brew to PATH for Apple Silicon
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        print_success "Homebrew installed"
    fi
}

# Install uv (fast Python package manager)
install_uv() {
    print_step "Checking uv..."
    if command -v uv &> /dev/null; then
        print_success "uv is already installed ($(uv --version))"
    else
        print_step "Installing uv via Homebrew..."
        brew install uv
        print_success "uv installed"
    fi
}

# Set up .env file with API key
setup_env() {
    print_step "Checking .env file..."

    # If .env exists and already has a real key, skip
    if [[ -f ".env" ]] && grep -q '^ANTHROPIC_API_KEY=sk-ant-' .env; then
        print_success ".env file exists with API key"
        return
    fi

    # Prompt for the key
    echo
    echo "An Anthropic API key is required for the LLM backend."
    echo "Get one at: https://console.anthropic.com/settings/keys"
    echo
    read -p "Paste your ANTHROPIC_API_KEY (or press Enter to skip): " api_key

    if [[ -n "$api_key" ]]; then
        cat > .env <<EOL
# API Keys for LLM backends
ANTHROPIC_API_KEY=${api_key}

# OpenAI (optional)
# OPENAI_API_KEY=sk-your-key-here

# Ollama (optional, local models)
# OLLAMA_HOST=http://localhost:11434
EOL
        print_success ".env created with API key"
    else
        if [[ ! -f ".env" ]]; then
            cp .env.example .env
        fi
        print_warning "Skipped — add your ANTHROPIC_API_KEY to .env before running the GUI"
    fi
}


# Install Python dependencies
install_python_deps() {
    print_step "Installing Python dependencies..."

    # Check if we're in the right directory
    if [[ ! -f "pyproject.toml" ]]; then
        print_error "pyproject.toml not found. Please run this script from the ccpp root directory."
        exit 1
    fi

    # Install main dependencies
    uv sync

    # Install dev dependencies (pytest, etc.)
    uv pip install pytest pytest-cov pytest-mock ruff

    print_success "Python dependencies installed"
}

# Generate MLX training data if missing (needed only for retraining)
generate_mlx_data() {
    if [[ -d "data/training/stage1_mlx" ]]; then
        print_success "MLX training data already exists"
        return
    fi

    if [[ ! -f "data/training/stage1.train.jsonl" ]]; then
        print_warning "No stage1 training data found - skipping MLX format generation"
        return
    fi

    print_step "Generating stage1 MLX training data (local reformatting, no API key needed)..."
    uv run python -m data.scripts.convert_to_mlx --stage 1
    print_success "Stage 1 MLX training data generated"
}

# Verify installation
verify_installation() {
    print_step "Verifying installation..."

    # Check Python imports
    if uv run python -c "from ccpp.llm.mlx_backend import MLXBackend; print('OK')" &> /dev/null; then
        print_success "Python imports working (MLX backend)"
    else
        print_warning "MLX backend import failed - this is expected on non-Apple Silicon"
    fi

    # Check Ollama installation (not running - just that it's available)
    if command -v ollama &> /dev/null; then
        print_success "Ollama is installed"
    else
        print_warning "Ollama not installed - install with: brew install ollama"
    fi
}

# Print usage instructions
print_usage() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}  Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "To start the GUI:"
    echo "  uv run python scripts/gui_client.py"
    echo "  (base models download automatically on first run)"
    echo
    echo "Other commands:"
    echo "  uv run pytest              # run tests"
    echo
    echo "Logs: /tmp/gui_debug.log, /tmp/prompt_logs.jsonl"
    echo
}

# Main
main() {
    echo -e "${BLUE}"
    echo "  ██████╗ ██████╗ ██╗     ██╗"
    echo " ██╔════╝██╔════╝██╔╝██╗  ██╔╝"
    echo " ██║     ██║     ╚═╝╚═╝  ██║ "
    echo " ██║     ██║     ██╗██╗  ██║ "
    echo " ╚██████╗╚██████╗╚═╝╚═╝  ██║ "
    echo "  ╚═════╝ ╚═════╝        ╚═╝ "
    echo -e "${NC}"
    echo " PII Masking System - Setup"
    echo

    check_macos
    install_homebrew
    install_uv
    setup_env
    install_python_deps
    generate_mlx_data
    verify_installation
    print_usage
}

main "$@"
