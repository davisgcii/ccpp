#!/bin/bash
set -e

echo "========================================="
echo "CC++ PII Masking Setup Script"
echo "========================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed"
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✅ uv installed successfully"
    echo ""
    echo "⚠️  Please restart your terminal and run this script again to continue setup."
    exit 0
else
    echo "✅ uv is already installed"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
uv sync
echo "✅ Python dependencies installed"

# Check if ollama is installed
echo ""
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed"
    echo ""
    echo "Please install Ollama from: https://ollama.com"
    echo ""
    echo "Platform-specific instructions:"
    echo "  - macOS: Download and install from https://ollama.com/download/mac"
    echo "  - Linux: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  - Windows: Download from https://ollama.com/download/windows"
    echo ""
    echo "After installing Ollama, run this script again to complete setup."
    exit 0
else
    echo "✅ Ollama is already installed"
fi

# Pull required Ollama models
echo ""
echo "Pulling Ollama models (this may take a while)..."
echo ""

models=("qwen2.5:0.5b" "qwen2.5:1.5b" "qwen2.5:3b")
for model in "${models[@]}"; do
    echo "Pulling $model..."
    if ollama pull "$model"; then
        echo "✅ $model pulled successfully"
    else
        echo "⚠️  Failed to pull $model (you can pull it later with: ollama pull $model)"
    fi
    echo ""
done

# Create .env file if it doesn't exist
echo ""
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  Please edit .env and add your API keys:"
    echo "   - ANTHROPIC_API_KEY=your_key_here"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your API keys (if not already done)"
echo "  2. Run the demo: uv run python scripts/demo.py"
echo "  3. Run interactive mode: uv run python scripts/demo.py -i"
echo ""
