#!/bin/bash
#
# CC++ PII Masking System - Setup Script
#
# This script installs all dependencies required to run the CC++ system:
# - Homebrew (if not installed)
# - uv (Python package manager)
# - Ollama (local LLM server)
# - Qwen3 models for classification and entity extraction
# - Python dependencies
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

# Install Ollama
install_ollama() {
    print_step "Checking Ollama..."

    # Minimum version for logprobs support
    MIN_VERSION="0.12.11"

    if command -v ollama &> /dev/null; then
        CURRENT_VERSION=$(ollama --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        print_success "Ollama is already installed (v${CURRENT_VERSION})"

        # Check version for logprobs support
        if [[ "$(printf '%s\n' "$MIN_VERSION" "$CURRENT_VERSION" | sort -V | head -n1)" != "$MIN_VERSION" ]]; then
            print_warning "Ollama v${CURRENT_VERSION} does not support logprobs (requires v${MIN_VERSION}+)"
            print_step "Upgrading Ollama..."
            brew upgrade ollama || true
        fi
    else
        print_step "Installing Ollama via Homebrew..."
        brew install ollama
        print_success "Ollama installed"
    fi
}

# Start Ollama service
start_ollama() {
    print_step "Starting Ollama service..."

    # Check if Ollama is already running
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        print_success "Ollama is already running"
        return 0
    fi

    # Start Ollama in background
    if [[ "$(uname)" == "Darwin" ]]; then
        # macOS: Use brew services
        brew services start ollama 2>/dev/null || true

        # Wait for Ollama to start
        print_step "Waiting for Ollama to start..."
        for i in {1..30}; do
            if curl -s http://localhost:11434/api/tags &> /dev/null; then
                print_success "Ollama is running"
                return 0
            fi
            sleep 1
        done

        # Try starting manually if brew services didn't work
        print_warning "Trying to start Ollama manually..."
        ollama serve &> /dev/null &
        sleep 3

        if curl -s http://localhost:11434/api/tags &> /dev/null; then
            print_success "Ollama is running"
            return 0
        fi

        print_error "Failed to start Ollama. Please start it manually with: ollama serve"
        return 1
    else
        # Linux: Start manually
        ollama serve &> /dev/null &
        sleep 3
        if curl -s http://localhost:11434/api/tags &> /dev/null; then
            print_success "Ollama is running"
            return 0
        fi
        print_error "Failed to start Ollama"
        return 1
    fi
}

# Pull required models
pull_models() {
    print_step "Pulling required Ollama models..."

    # Models used by the system:
    # - qwen3:0.6b - Stage 1 classification (fast, lightweight)
    # - qwen3:1.7b - Stage 2 entity extraction (more accurate)
    # Note: Use think=False in API calls to disable thinking mode
    MODELS=("qwen3:0.6b" "qwen3:1.7b")

    for MODEL in "${MODELS[@]}"; do
        # Check if model is already downloaded
        if ollama list 2>/dev/null | grep -q "$MODEL"; then
            print_success "Model $MODEL is already downloaded"
        else
            print_step "Downloading $MODEL (this may take a few minutes)..."
            ollama pull "$MODEL"
            print_success "Model $MODEL downloaded"
        fi
    done
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
    if uv run python -c "from ccpp.llm.ollama_backend import OllamaBackend; print('OK')" &> /dev/null; then
        print_success "Python imports working"
    else
        print_error "Python imports failed"
        return 1
    fi

    # Check Ollama connection
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        print_success "Ollama connection working"
    else
        print_warning "Ollama not responding - make sure to start it with: ollama serve"
    fi

    # Check model availability
    MODELS_OK=true
    for MODEL in "qwen3:0.6b" "qwen3:1.7b"; do
        if ollama list 2>/dev/null | grep -q "$MODEL"; then
            print_success "Model $MODEL available"
        else
            print_warning "Model $MODEL not found - run: ollama pull $MODEL"
            MODELS_OK=false
        fi
    done
}

# Print usage instructions
print_usage() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}  Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "To start the GUI:"
    echo "  uv run python scripts/gui_client.py"
    echo
    echo "To run tests:"
    echo "  uv run pytest"
    echo
    echo "If Ollama isn't running, start it with:"
    echo "  brew services start ollama"
    echo "  # or"
    echo "  ollama serve"
    echo
    echo "Logs are available at:"
    echo "  /tmp/gui_debug.log"
    echo "  /tmp/prompt_logs.jsonl"
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
    start_ollama
    pull_models
    install_python_deps
    verify_installation
    print_usage
}

main "$@"
