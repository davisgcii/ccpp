#!/bin/bash
#
# CC++ PII Masking System - Setup Script
#
# This script installs all dependencies required to run the CC++ system:
# - Homebrew (if not installed)
# - uv (Python package manager)
# - Ollama (local LLM server) - checks installation only
# - Python dependencies
#
# The default backend is MLX (Apple Silicon). For Ollama backend,
# you'll need to manually start Ollama and pull the required models.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
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

# Check/Install Ollama (for optional Ollama backend)
install_ollama() {
    print_step "Checking Ollama (optional, for Ollama backend)..."

    # Minimum version for logprobs support
    MIN_VERSION="0.12.11"

    if command -v ollama &> /dev/null; then
        CURRENT_VERSION=$(ollama --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        print_success "Ollama is installed (v${CURRENT_VERSION})"

        # Check version for logprobs support
        if [[ "$(printf '%s\n' "$MIN_VERSION" "$CURRENT_VERSION" | sort -V | head -n1)" != "$MIN_VERSION" ]]; then
            print_warning "Ollama v${CURRENT_VERSION} does not support logprobs (requires v${MIN_VERSION}+)"
            print_warning "Run 'brew upgrade ollama' to upgrade"
        fi
    else
        print_step "Installing Ollama via Homebrew..."
        brew install ollama
        print_success "Ollama installed"
    fi

    # Inform user about required models for Ollama backend
    echo
    print_warning "To use the Ollama backend, you'll need to:"
    echo "  1. Start Ollama: ollama serve (or brew services start ollama)"
    echo "  2. Pull models: ollama pull qwen3:0.6b && ollama pull qwen3:1.7b"
    echo "  3. Update configs/default.yaml to use 'ollama' backend"
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
    echo "Default backend: MLX (Apple Silicon)"
    echo
    echo "To start the GUI:"
    echo "  uv run python scripts/gui_client.py"
    echo
    echo "To run tests:"
    echo "  uv run pytest"
    echo
    echo "Logs are available at:"
    echo "  /tmp/gui_debug.log"
    echo "  /tmp/prompt_logs.jsonl"
    echo
    echo -e "${YELLOW}Optional: Ollama backend${NC}"
    echo "  1. Start Ollama: ollama serve"
    echo "  2. Pull models: ollama pull qwen3:0.6b && ollama pull qwen3:1.7b"
    echo "  3. Edit configs/default.yaml: set backend to 'ollama'"
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
    install_ollama
    install_python_deps
    verify_installation
    print_usage
}

main "$@"
