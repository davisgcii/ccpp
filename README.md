# CC++ PII Masking

A CC++-inspired streaming exchange classifier for PII detection and masking in black-box hosted LLMs.

## ⚠️ Project Status

**ACTIVE DEVELOPMENT** - Core pipeline implemented with working two-stage cascade:

✅ **Working**:
- Stage 1 classification using MLX sequence log-likelihood (default, Apple Silicon)
- Stage 2 entity extraction with MLX text generation
- Ollama backend available as cross-platform alternative (native logprobs)
- GUI client with real-time visualization
- Fast heuristics (regex patterns)

⏸️ **Not Started**:
- Training data generation
- Model fine-tuning
- Evaluation and calibration

See [TODO.md](TODO.md) for detailed progress tracking.

## Overview

This project implements a two-stage cascade for streaming PII detection and masking:

- **Stage 1 (Router)**: Fast classification using MLX with Qwen3-0.6B-4bit (sequence log-likelihood)
- **Stage 2 (Redactor)**: Accurate entity extraction using MLX with Qwen3-1.7B

Ollama backend available as cross-platform alternative with native logprobs API.

## Features

- **Per-token classification**: Runs on every new token/chunk (not fixed windows)
- **Stream break detection**: Timeout-based (default 2s) for natural conversation boundaries
- **Three-condition masking**: any_risk_in_buffer OR ema≥T_high OR strong_heuristic_match
- **EMA natural decay**: Cross-break PII detection without manual reset
- **Calibrated probabilities**: MLX uses sequence log-likelihood, Ollama uses native logprobs API
- **LLM harness**: Unified interface for MLX (default), Ollama (cross-platform), and API backends (Claude, GPT)

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/davisgcii/ccpp.git
cd ccpp

# Install dependencies
uv sync

# Configure your API keys (optional, for Anthropic backend)
# Edit .env and add your ANTHROPIC_API_KEY
```

### Run GUI Client

```bash
# Launch interactive GUI (uses MLX backend by default)
uv run python scripts/gui_client.py

# GUI will be available at http://127.0.0.1:7860
# Logs available at /tmp/gui_debug.log
```

**Note**: Default backend is MLX (Apple Silicon). For Ollama backend, run `ollama pull qwen3:0.6b && ollama pull qwen3:1.7b` and update `configs/default.yaml`.

## Configuration

CC++ uses a flexible YAML-based configuration system. Default backend is **MLX** (Apple Silicon). Ollama backend available as cross-platform alternative.

### Current Configuration (`configs/default.yaml`)

**Backend**: MLX (Apple Silicon, local inference)
- **Stage 1 Router**: `mlx-community/Qwen3-0.6B-4bit` with sequence log-likelihood (fast)
- **Stage 2 Redactor**: `Qwen/Qwen3-1.7B-MLX-8bit` with text generation (accurate)

**Key Parameters**:
- **Stream break timeout**: `2000ms` (2 seconds) - wait time before masking decision
- **EMA beta**: `0.85` - smoothing factor for risk scores
- **Thresholds**:
  - `t_high: 0.6` - escalate to Stage 2 when EMA crosses this
  - `t_low: 0.3` - de-escalate when EMA drops below this
  - `risk_threshold: 0.7` - individual token P(RISK) threshold for immediate flagging
- **Heuristics**: Enabled (regex patterns for emails, phones, SSNs, API keys)

**Ollama Alternative**: Set `backend: ollama`, use `qwen3:0.6b`/`qwen3:1.7b` models, set `sequence_loglikelihood.enabled: false`. Uses native logprobs API with `think=False`.

See [Configuration Guide](docs/CONFIG.md) for complete reference and `configs/default.yaml` for full configuration.

## Testing

The project uses pytest with three test tiers:

1. **Unit tests** (fast, mocked dependencies) - default
2. **Integration tests** (real APIs/services) - optional
3. **End-to-end tests** (full pipeline) - future

### Run All Tests (Unit Only)

```bash
uv run pytest                    # All unit tests
uv run pytest --cov=src/ccpp    # With coverage
```

### Run Integration Tests

Integration tests verify connectivity with real services:

```bash
# Prerequisites
ollama serve
ollama pull qwen3:1.7b
export ANTHROPIC_API_KEY=sk-ant-...

# Run integration tests
uv run pytest -m integration
```

**Note**: Integration tests are skipped by default. They only run when:
- Marked explicitly with `-m integration`
- Required services are available (Ollama running, API keys set)
- Cost is minimal (~$0.001 total for Anthropic tests)

### Run Tests by Category

```bash
# Unit tests only (default)
uv run pytest

# Integration tests only
uv run pytest -m integration

# Exclude slow tests
uv run pytest -m "not slow"
```

### Run Specific Test Files

```bash
# Core components
uv run pytest tests/test_types.py
uv run pytest tests/test_llm_harness.py
uv run pytest tests/test_heuristics.py

# Pipeline stages
uv run pytest tests/test_stage1_router.py
uv run pytest tests/test_stage2_redactor.py

# Configuration
uv run pytest tests/test_config.py

# Integration (requires services)
uv run pytest tests/test_integration.py
```

See [Testing Guide](docs/TESTING.md) for detailed testing documentation.

### Coverage Report

```bash
# Run tests with coverage report
uv run pytest --cov=src/ccpp --cov-report=html --cov-report=term-missing
```

## Architecture

See `CLAUDE.md` for detailed architecture documentation.

## License

[Add your license here]
