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
git clone https://github.com/davisgcii/ccpp.git
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

## Configuration

CC++ uses a flexible YAML-based configuration system for managing models, backends, and streaming parameters. The system is designed for **real-time voice conversations** where natural pauses occur.

### Configuration Files

The system uses three hierarchical configs:

#### `configs/default.yaml` - Base Configuration

**When to use:** Production deployments, voice conversation apps

**Key settings:**
- **Stage 1 (Fast Router)**: Ollama with `qwen3:1.7b` - lightweight model for per-token risk classification
- **Stage 2 (Accurate Redactor)**: Ollama with `qwen3:4b` - larger model for precise entity extraction
- **Stream break timeout**: `2000ms` (2 seconds) - handles natural voice pauses before triggering masking
- **EMA beta**: `0.85` - smoothing factor for risk scores (higher = more stable, less reactive)
- **Thresholds**:
  - `t_high: 0.6` - escalate to Stage 2 when EMA crosses this threshold
  - `t_low: 0.3` - de-escalate when EMA drops below this threshold
  - `risk_threshold: 0.7` - individual token P(RISK) to trigger immediate attention
- **Heuristics**: Enabled for fast regex-based PII detection (emails, SSNs, API keys, etc.)

**Use case:** Baseline for all deployments. Optimized for voice conversations with natural pauses.

```bash
# Use default config
python scripts/demo_guard.py

# Or explicitly
export CCPP_ENV=default
python scripts/demo_guard.py
```

#### `configs/dev.yaml` - Development Configuration

**When to use:** Local development, rapid iteration, testing

**Overrides:**
- **Stream break timeout**: `1000ms` (1 second) - faster iteration during development
- **Buffer size**: `1024` chars (vs 2048 in default) - reasonable for dev, still large enough
- **Logging**: `DEBUG` level - verbose output for debugging
- **Stage 1/2**: Still uses Ollama (local, no API costs)

**Why these settings:**
- Faster timeouts reduce waiting during development (but still voice-appropriate)
- Buffer still large enough to avoid mid-speech interruptions
- Debug logging helps identify issues quickly
- Local models avoid API costs during iteration

**Use case:** When building features, testing locally, debugging issues.

```bash
# Use dev config
export CCPP_ENV=dev
python scripts/demo_guard.py

# Or in Python
from ccpp.config import load_config
config = load_config(environment="dev")
```

#### `configs/prod.yaml` - Production Configuration

**When to use:** Production deployments with cloud APIs

**Overrides:**
- **Stage 1**: Anthropic `claude-haiku-4-5-20251001` - fast, low-cost API (~$0.25/million tokens)
- **Stage 2**: Anthropic `claude-haiku-4-5-20251001` - accurate, higher-quality API
- **Stream break timeout**: `2000ms` (2 seconds) - same as default (voice-appropriate)
- **Logging**: `INFO` level - production-appropriate logging
- **Timeouts**: Cloud API timeouts (10s Stage 1, 30s Stage 2)

**Why these settings:**
- Cloud APIs scale better than local models (no GPU required)
- Haiku is fast and cost-effective for real-time use
- Conservative timeouts handle voice pauses appropriately
- INFO logging reduces noise in production logs

**Use case:** Production deployments, high-scale applications, when GPU unavailable.

```bash
# Use prod config
export CCPP_ENV=prod
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/demo_guard.py
```

### Key Configuration Settings Explained

#### Stream Break Timeout (`stream_break_timeout_ms`)

**What it does:** Time to wait after receiving the last token before deciding whether to mask.

**Why it matters for voice:**
- Voice conversations have natural pauses (thinking, breathing, interruptions)
- Too short: breaks mid-sentence, partial PII might get split across breaks
- Too long: user waits unnecessarily for masked output

**Values:**
- `default.yaml`: 2000ms (2 seconds) - handles most natural voice pauses
- `dev.yaml`: 1000ms (1 second) - faster iteration during development
- `prod.yaml`: 2000ms (2 seconds) - same as default

**Example scenario:**
```
User: "My email is..." [800ms pause while thinking] "john@example.com"
       └─ With 2000ms timeout, both parts stay in buffer until pause exceeds 2s
       └─ With 500ms timeout, "My email is..." would trigger masking prematurely
```

#### Holdback Buffer Size (`holdback_buffer_size`)

**What it does:** Maximum characters to accumulate before forcing a masking decision (safety net only).

**Why it exists:**
- Prevents unbounded memory growth if someone speaks continuously for a very long time
- Safety limit for edge cases (e.g., someone reading a long document aloud)
- **NOT the primary trigger** - that's the stream break timeout

**Important:** For voice conversations, you should rely on the **stream break timeout** (2s pause), not the buffer size. The buffer should be large enough to never trigger during normal speech.

**Values:**
- `default.yaml`: 2048 chars (~5-10 minutes of continuous speech)
- `dev.yaml`: 1024 chars (still large enough for testing)
- `prod.yaml`: 2048 chars (same as default)

**Example of what we avoid:**
```
❌ Buffer too small (512 chars):
User: "My address is 123 Main Street, Apartment 4B, Springfield..." [hits 512 char limit]
      └─ FORCED masking decision mid-sentence! Buffer full interrupt.

✅ Buffer large enough (2048 chars):
User: "My address is 123 Main Street, Apartment 4B, Springfield..." [2s pause]
      └─ Natural break detected via timeout. Smooth masking decision.
```

**When buffer limit matters:**
- Someone reading a long passage without pausing (rare)
- Continuous speech for multiple minutes (edge case)
- Should almost never trigger in normal conversation

**Rule of thumb:** Set buffer size to be **4x larger** than your longest expected utterance. For voice, 2048 chars handles ~300-400 words of continuous speech.

#### EMA Beta (`ema_beta`)

**What it does:** Exponential Moving Average smoothing factor for risk scores.

**Why it matters:**
- Prevents jitter from single-token spikes
- Maintains context across multiple tokens
- Enables cross-break PII detection

**Value:** `0.85` (higher = more smoothing, slower to react)

**Formula:** `ema = beta * ema + (1 - beta) * new_risk`

#### Thresholds

**`t_high` (0.6)**: EMA threshold to escalate to Stage 2 (expensive entity extraction)
- When EMA crosses 0.6, buffer gets expensive analysis
- Higher = fewer false positives, but might miss subtle PII

**`t_low` (0.3)**: EMA threshold to de-escalate
- When EMA drops below 0.3, stop escalating
- Creates hysteresis (prevents oscillation)

**`risk_threshold` (0.7)**: Individual token P(RISK) to set `any_risk_in_buffer` flag
- Single token with P(RISK) ≥ 0.7 triggers immediate attention
- Used alongside EMA (if either condition met, mask)

#### Model Selection

**Stage 1 (Router):**
- Default: `qwen3:1.7b` (local, ~1.7B parameters) - fast per-token classification
- Prod: `claude-haiku-4-5` - cloud API, fast and cheap

**Stage 2 (Redactor):**
- Default: `qwen3:4b` (local, ~4B parameters) - accurate entity extraction
- Prod: `claude-haiku-4-5` - cloud API, higher accuracy

**Why different models:**
- Stage 1 runs on every token → needs to be fast (smaller model)
- Stage 2 only runs at breaks when needed → can be slower/larger (better accuracy)

### How to Invoke Configs

#### 1. Via Environment Variable (Recommended)

```bash
# Development
export CCPP_ENV=dev
python scripts/demo_guard.py

# Production
export CCPP_ENV=prod
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/demo_guard.py
```

#### 2. In Python Code

```python
from ccpp.config import load_config, get_stage1_config, get_stage2_config
from ccpp.infer.stage1_router import Stage1Router
from ccpp.infer.stage2_redactor import Stage2Redactor

# Load config
config = load_config(environment="dev")  # or "prod", or None for default

# Create components
router = Stage1Router(
    llm_config=get_stage1_config(config),
    mock_mode=False
)

redactor = Stage2Redactor(
    llm_config=get_stage2_config(config),
    mock_mode=False
)

# Access streaming params
timeout = config.streaming.stream_break_timeout_ms  # 1000 for dev
t_high = config.streaming.t_high  # 0.6
```

#### 3. Runtime Overrides via Environment Variables

Override specific settings without changing config files:

```bash
# Override stream break timeout
export CCPP_STREAMING__STREAM_BREAK_TIMEOUT_MS=1500

# Override Stage 1 backend
export CCPP_STAGE1__BACKEND=anthropic
export CCPP_STAGE1__MODEL_NAME=claude-haiku-4-5-20251001

# Override thresholds
export CCPP_STREAMING__T_HIGH=0.7

# Run with overrides
python scripts/demo_guard.py
```

**Syntax:** `CCPP_<section>__<key>=<value>` (double underscores for nesting)

#### 4. Runtime Overrides via Dict

```python
from ccpp.config import load_config

# Load base config with overrides
config = load_config(
    environment="dev",
    overrides={
        "streaming": {
            "stream_break_timeout_ms": 1500,  # Custom timeout
            "t_high": 0.7  # More sensitive
        }
    }
)
```

### Common Scenarios

#### Local Development (Ollama)
```bash
export CCPP_ENV=dev
ollama serve
python scripts/demo_guard.py
```
- Uses `qwen3:1.7b` and `qwen3:4b` (local)
- Fast iteration (1s timeout)
- Debug logging

#### Production (Cloud APIs)
```bash
export CCPP_ENV=prod
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/demo_guard.py
```
- Uses Claude Haiku (API)
- Scalable (no local GPU needed)
- Voice-appropriate timeouts (2s)

#### Testing with Longer Pauses
```bash
# Override timeout for slower speakers
export CCPP_ENV=dev
export CCPP_STREAMING__STREAM_BREAK_TIMEOUT_MS=3000  # 3 seconds
python scripts/demo_guard.py
```

#### More Aggressive PII Detection
```bash
# Lower thresholds for higher sensitivity
export CCPP_ENV=dev
export CCPP_STREAMING__T_HIGH=0.4
export CCPP_STREAMING__RISK_THRESHOLD=0.5
python scripts/demo_guard.py
```

See [Configuration Guide](docs/CONFIG.md) for complete reference and advanced usage.

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
