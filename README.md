# CC++ PII Masking

A CC++-inspired streaming exchange classifier for PII detection and masking in black-box hosted LLMs.

## Overview

This project implements a two-stage cascade for streaming PII detection and masking:

- **Stage 1 (Router)**: Fast per-token classification using Qwen3-1.7B
- **Stage 2 (Redactor)**: Accurate entity extraction using Qwen3-4B

## Features

- **Per-token classification**: Runs on every new token/chunk (not fixed windows)
- **Stream break detection**: Timeout-based (500ms default) for natural conversation boundaries
- **Three-condition masking**: any_risk_in_buffer OR ema≥T_high OR strong_heuristic_match
- **EMA natural decay**: Cross-break PII detection without manual reset
- **LLM harness**: Unified interface for Ollama (local) and API backends (Claude, GPT)

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ccpp.git
cd ccpp

# Run the setup script (installs uv, dependencies, and Ollama models)
./scripts/setup.sh

# Configure your API keys (optional, for interactive client)
# Edit .env and add your ANTHROPIC_API_KEY
```

The setup script will:
1. Install `uv` if not already installed
2. Install Python dependencies via `uv sync`
3. Check for Ollama installation (with platform-specific instructions)
4. Pull required Ollama models (qwen2.5:0.5b, qwen2.5:1.5b, qwen2.5:3b)
5. Create a `.env` file from `.env.example`

### Run Demo

```bash
# Run with mock mode (default)
uv run python scripts/demo.py

# Run with Ollama backend
uv run python scripts/demo.py --backend ollama --stage1-config configs/stage1_llm.yaml --stage2-config configs/stage2_llm.yaml

# Interactive mode
uv run python scripts/demo.py -i
```

## Architecture

See `CLAUDE.md` for detailed architecture documentation.

## License

[Add your license here]
