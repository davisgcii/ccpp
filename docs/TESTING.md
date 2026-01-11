# Testing Guide

## Overview

The CC++ test suite is organized into three tiers:

1. **Unit tests** (fast, no external dependencies)
2. **Integration tests** (may require Ollama/API keys)
3. **End-to-end tests** (full pipeline validation)

## Running Tests

### Run all unit tests (default)
```bash
# Run all tests except integration
uv run pytest

# With coverage
uv run pytest --cov=src/ccpp --cov-report=html
```

### Run integration tests
```bash
# Run only integration tests
uv run pytest -m integration

# Run all tests including integration
uv run pytest -m "not slow"
```

### Run specific test files
```bash
# Test a specific module
uv run pytest tests/test_llm_harness.py

# Test a specific class
uv run pytest tests/test_llm_harness.py::TestOllamaBackend

# Test a specific function
uv run pytest tests/test_llm_harness.py::TestOllamaBackend::test_ollama_generate
```

## Integration Tests

Integration tests verify connectivity with real services. They are **skipped by default** and only run when explicitly requested.

### Prerequisites

#### For Ollama Tests
```bash
# Start Ollama
ollama serve

# Pull required models
ollama pull qwen3:1.7b
```

#### For Anthropic Tests
```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-...
```

#### For OpenAI Tests
```bash
# Set API key
export OPENAI_API_KEY=sk-...
```

### Running Integration Tests

```bash
# Run all integration tests (requires prerequisites above)
uv run pytest -m integration -v

# Run only Ollama integration tests
uv run pytest -m integration tests/test_integration.py::TestOllamaIntegration

# Run only Anthropic integration tests
uv run pytest -m integration tests/test_integration.py::TestAnthropicIntegration
```

### Cost Considerations

- **Ollama**: Free (runs locally)
- **Anthropic Haiku**: ~$0.0001 per test (~$0.001 total for all tests)
- **OpenAI GPT-4o-mini**: ~$0.0001 per test

Integration tests use minimal tokens to keep costs low.

## Test Organization

```
tests/
├── conftest.py               # Shared fixtures
├── test_heuristics.py        # Fast heuristics (unit)
├── test_llm_harness.py       # LLM backends (unit, mocked)
├── test_stage1_router.py     # Stage 1 classifier (unit)
├── test_stage2_redactor.py   # Stage 2 redactor (unit)
├── test_types.py             # Type definitions (unit)
├── test_config.py            # Configuration (unit)
└── test_integration.py       # Integration tests (requires services)
```

## Writing Tests

### Unit Tests (Preferred)

Use mocks for external dependencies:

```python
from unittest.mock import Mock, patch

@patch('ollama.Client')
def test_ollama_backend(mock_client_class):
    """Test Ollama backend with mocked client."""
    mock_client = Mock()
    mock_client.chat.return_value = {"message": {"content": "Hello"}}
    mock_client_class.return_value = mock_client

    backend = OllamaBackend(model_name="qwen3:1.7b")
    result = backend.generate([{"role": "user", "content": "Test"}], config)

    assert result == "Hello"
```

### Integration Tests

Mark with `@pytest.mark.integration` and use fixtures to check prerequisites:

```python
import pytest

@pytest.mark.integration
class TestOllamaIntegration:
    @pytest.fixture(scope="class")
    def check_ollama_available(self):
        """Skip if Ollama not available."""
        try:
            import ollama
            client = ollama.Client()
            client.list()
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")

    def test_ollama_generate(self, check_ollama_available):
        """Test real Ollama generation."""
        backend = OllamaBackend(model_name="qwen3:1.7b")
        result = backend.generate([...], config)
        assert isinstance(result, str)
```

## Best Practices

### 1. Mock External Dependencies

✅ **Good**: Mock the network call
```python
@patch('ollama.Client')
def test_feature(mock_client_class):
    ...
```

❌ **Bad**: Require service to be running
```python
def test_feature():
    backend = OllamaBackend(...)  # Fails if Ollama not running
```

### 2. Use Fixtures for Common Setup

```python
@pytest.fixture
def stage1_config():
    """Standard Stage 1 config for tests."""
    return {
        "backend": "ollama",
        "model_name": "qwen3:1.7b",
        "timeout": 60,
    }
```

### 3. Test Behavior, Not Implementation

✅ **Good**: Test the output
```python
def test_classify_pii():
    result = router.classify([], "My email is test@test.com")
    assert result.score > 0.5  # Detects PII
```

❌ **Bad**: Test internal details
```python
def test_classify_pii():
    router.classify([], "My email is test@test.com")
    assert router._internal_cache_size == 1  # Implementation detail
```

### 4. Keep Tests Fast

- Unit tests should run in **< 1 second**
- Integration tests can take **< 5 seconds**
- Use `pytest -m "not slow"` to skip slow tests during development

### 5. Document Prerequisites

```python
@pytest.mark.integration
@pytest.mark.requires_ollama
def test_ollama_feature():
    """Test Ollama feature.

    Prerequisites:
    - Ollama running on localhost:11434
    - Model qwen3:1.7b pulled
    """
    ...
```

## Continuous Integration

Our CI pipeline runs:

1. **All unit tests** (fast, every commit)
2. **Integration tests** (slower, on main branch only)
3. **Coverage reporting** (must maintain > 80% coverage)

### GitHub Actions Example

```yaml
- name: Run unit tests
  run: uv run pytest -m "not integration"

- name: Run integration tests
  if: github.ref == 'refs/heads/main'
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: uv run pytest -m integration
```

## Troubleshooting

### "Ollama not accessible"
- Check Ollama is running: `ollama list`
- Verify connection: `curl http://localhost:11434/api/tags`

### "Model not found"
- Pull the model: `ollama pull qwen3:1.7b`
- Check available models: `ollama list`

### "API key required"
- Set environment variable: `export ANTHROPIC_API_KEY=...`
- Or create `.env` file with keys

### Test hangs
- Some tests may timeout if service is slow
- Use `pytest --timeout=10` to set global timeout
- Check firewall/network settings

## Coverage Goals

- **Overall**: > 80%
- **Core modules** (stage1, stage2, heuristics): > 90%
- **Integration code**: > 70%
- **Scripts**: > 60%

View coverage report:
```bash
uv run pytest --cov=src/ccpp --cov-report=html
open htmlcov/index.html
```
