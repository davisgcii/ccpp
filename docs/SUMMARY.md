# Testing & Configuration Summary

This document summarizes the testing infrastructure and configuration system added to CC++.

## What Was Added

### 1. Integration Tests (`tests/test_integration.py`)

Real API/service connectivity tests that are **skipped by default**:

- **Ollama tests**: Verify local model generation and logit extraction
- **Anthropic tests**: Verify Claude API connectivity and responses
- **OpenAI tests**: Verify GPT API connectivity and responses

**Key features:**
- Only run when explicitly marked: `pytest -m integration`
- Auto-skip if prerequisites missing (service not running, API key not set)
- Minimal token usage to keep costs low (~$0.001 total)
- Clear error messages about what's missing

**Example:**
```bash
# Prerequisites
ollama serve
ollama pull qwen3:1.7b
export ANTHROPIC_API_KEY=sk-ant-...

# Run integration tests
uv run pytest -m integration -v
```

### 2. Configuration System (`src/ccpp/config.py`)

Hierarchical YAML-based configuration with environment support:

**Features:**
- Environment-specific configs (dev, prod, custom)
- Runtime overrides via dict or environment variables
- Deep merging of configs (inheritance)
- Dot-notation access to config values
- Type-safe extraction helpers for Stage 1/2

**Example:**
```python
from ccpp.config import load_config, get_stage1_config

# Load config
config = load_config(environment="dev")

# Access values
print(config.stage1.backend)           # Dot notation
print(config.streaming.t_high)         # Nested access

# Extract for components
stage1_config = get_stage1_config(config)
router = Stage1Router(llm_config=stage1_config, mock_mode=False)
```

### 3. Configuration Files

**`configs/default.yaml`** - Base configuration:
- Stage 1: Ollama with Qwen3-1.7B
- Stage 2: Ollama with Qwen3-4B
- Streaming parameters (timeouts, thresholds, EMA settings)
- Heuristics configuration
- Masking output formats

**`configs/dev.yaml`** - Development overrides:
- Faster timeouts (300ms stream breaks)
- Smaller buffers (256 chars)
- DEBUG logging
- Optimized for rapid iteration

**`configs/prod.yaml`** - Production overrides:
- Anthropic APIs (Haiku for Stage 1, Sonnet for Stage 2)
- Conservative timeouts (500ms)
- INFO logging
- Optimized for scalability and accuracy

### 4. Config Tests (`tests/test_config.py`)

Comprehensive tests for configuration system:
- Config object access (dot notation, dict access)
- Deep merging of nested dicts
- Environment variable overrides (CCPP_* prefix)
- Config loading (default, environment-specific, custom)
- Config extraction helpers

**All 21 config tests pass.**

### 5. Documentation

**`docs/TESTING.md`** - Complete testing guide:
- How to run different test types
- Prerequisites for integration tests
- Writing unit vs integration tests
- Best practices and patterns
- CI/CD integration examples
- Troubleshooting common issues

**`docs/CONFIG.md`** - Complete configuration guide:
- Configuration file structure
- Loading configs in Python
- Environment-specific overrides
- Runtime overrides via env vars
- Common configuration patterns
- Customization examples
- Best practices

## Test Results

### Before
- 92 tests passing (all unit tests with mocks)
- No integration tests
- No configuration system

### After
- **113 tests passing** (92 original + 21 config tests)
- **6 integration tests** (skipped by default, run when marked)
- Full configuration system with environment support

### Test Breakdown
```
tests/test_heuristics.py:        13 passed
tests/test_llm_harness.py:       22 passed (all mocked)
tests/test_stage1_router.py:     16 passed
tests/test_stage2_redactor.py:   23 passed
tests/test_types.py:             18 passed
tests/test_config.py:            21 passed ← NEW
tests/test_integration.py:        6 skipped (integration) ← NEW

Total: 113 passed, 6 skipped
```

## Usage Examples

### Running Tests

```bash
# Default: all unit tests (fast)
uv run pytest

# With integration tests (requires services)
uv run pytest -m integration

# Specific test file
uv run pytest tests/test_config.py -v

# With coverage
uv run pytest --cov=src/ccpp --cov-report=html
```

### Using Configuration

```python
from ccpp.config import load_config, get_stage1_config, get_stage2_config
from ccpp.infer.stage1_router import Stage1Router
from ccpp.infer.stage2_redactor import Stage2Redactor

# Load dev config
config = load_config(environment="dev")

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
timeout = config.streaming.stream_break_timeout_ms
t_high = config.streaming.t_high
```

### Environment Variable Overrides

```bash
# Override via env vars
export CCPP_STAGE1__BACKEND=anthropic
export CCPP_STAGE1__MODEL_NAME=claude-haiku-4-5-20251001
export CCPP_STREAMING__T_HIGH=0.7

# Run with overrides
python scripts/demo_guard.py

# Or set environment
export CCPP_ENV=prod
python scripts/demo_guard.py
```

## Benefits

### 1. Confidence in Real Services
- Integration tests verify actual connectivity
- Catch issues with API changes, network problems, etc.
- Validate response formats from real services

### 2. Flexible Configuration
- Easy to swap models without code changes
- Environment-specific settings (dev vs prod)
- Runtime overrides for experimentation
- Centralized parameter tuning

### 3. Development Velocity
- Fast unit tests (< 1 second total)
- Optional integration tests (only when needed)
- Clear separation of concerns
- Easy to test new configurations

### 4. Production Readiness
- Production config with cloud APIs
- Conservative settings for stability
- Proper logging levels
- Easy to deploy with different configs

## Best Practices Applied

### Testing
✅ Unit tests by default (fast, no dependencies)
✅ Integration tests optional (explicit opt-in)
✅ Clear prerequisites and error messages
✅ Minimal cost for API tests
✅ Comprehensive mocking for unit tests

### Configuration
✅ Hierarchical with inheritance (DRY)
✅ Environment-specific overrides
✅ Runtime flexibility (env vars, dict overrides)
✅ Type-safe extraction helpers
✅ Well-documented with examples

### Code Quality
✅ 113 tests passing (100% pass rate)
✅ Clear separation: unit vs integration
✅ Comprehensive documentation
✅ Easy to extend (add new configs, tests)
✅ Follows pytest best practices

## Next Steps

### For Development
1. Use `configs/dev.yaml` for local development
2. Run unit tests frequently: `uv run pytest`
3. Occasionally verify integration: `uv run pytest -m integration`

### For Production
1. Use `configs/prod.yaml` or create custom config
2. Set `CCPP_ENV=prod` environment variable
3. Configure API keys via environment variables
4. Monitor logs (set to INFO level)

### For Testing
1. Write unit tests for new features (with mocks)
2. Add integration tests for new backends
3. Keep integration tests lightweight
4. Document prerequisites clearly

## Questions?

See detailed guides:
- [Testing Guide](TESTING.md) - Complete testing documentation
- [Configuration Guide](CONFIG.md) - Complete configuration documentation
- [README](../README.md) - Quick start and overview
