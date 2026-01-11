#!/bin/bash
set -e

echo "========================================="
echo "CC++ PII Masking Setup Script"
echo "========================================="
echo ""

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew is not installed"
    echo "Please install Homebrew first: https://brew.sh"
    echo "Run: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
else
    echo "✅ Homebrew is installed"
fi

# Check if uv is installed
echo ""
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed"
    echo "Installing uv via Homebrew..."
    brew install uv
    echo "✅ uv installed successfully"
else
    echo "✅ uv is already installed"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
uv sync --all-extras
echo "✅ Python dependencies installed (including dev/test dependencies)"

# Check if ollama is installed
echo ""
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed"
    echo "Installing Ollama via Homebrew..."
    brew install ollama
    echo "✅ Ollama installed successfully"
    echo ""
    echo "⚠️  Starting Ollama service..."
    brew services start ollama
    echo "Waiting for Ollama to start..."
    sleep 3
else
    echo "✅ Ollama is already installed"
fi

# Pull required Ollama models
echo ""
echo "Pulling Ollama models (this may take a while)..."
echo ""

models=("qwen3:0.6b" "qwen3:1.7b" "qwen3:4b")
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
