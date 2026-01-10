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
1. Check for Homebrew installation
2. Install `uv` via Homebrew if not already installed
3. Install Python dependencies via `uv sync`
4. Install Ollama via Homebrew if not already installed
5. Pull required Ollama models (qwen3:0.6b, qwen3:1.7b, qwen3:4b)
6. Create a `.env` file from `.env.example`

### Run Demo

```bash
# Run with mock mode (default)
uv run python scripts/demo.py

# Run with Ollama backend
uv run python scripts/demo.py --backend ollama --stage1-config configs/stage1_llm.yaml --stage2-config configs/stage2_llm.yaml

# Interactive mode
uv run python scripts/demo.py -i
```

## Testing

The project uses pytest for testing. Tests are organized by markers for different categories.

### Run All Tests

```bash
uv run pytest
```

### Run Tests by Category

```bash
# Run only unit tests (fast, no external dependencies)
uv run pytest -m unit

# Run integration tests (may use external services)
uv run pytest -m integration

# Run tests that require Ollama (ensure Ollama is running)
uv run pytest -m requires_ollama

# Run tests that require API keys (ensure .env is configured)
uv run pytest -m requires_api

# Exclude slow tests
uv run pytest -m "not slow"
```

### Run Specific Test Files

```bash
# Test types and core data structures
uv run pytest tests/test_types.py

# Test LLM harness
uv run pytest tests/test_llm_harness.py

# Test heuristics
uv run pytest tests/test_heuristics.py

# Test Stage 1 router
uv run pytest tests/test_stage1_router.py

# Test Stage 2 redactor
uv run pytest tests/test_stage2_redactor.py
```

### Coverage Report

```bash
# Run tests with coverage report
uv run pytest --cov=src/ccpp --cov-report=html --cov-report=term-missing
```

## Architecture

See `CLAUDE.md` for detailed architecture documentation.

## License

[Add your license here]
