# Configuration Guide

## Overview

CC++ uses a hierarchical YAML-based configuration system that supports:

- **Environment-specific configs** (dev, prod, etc.)
- **Runtime overrides** (programmatic or via environment variables)
- **Centralized model selection** (easily swap models without code changes)
- **Streaming parameter tuning** (timeouts, thresholds, etc.)

## Configuration Files

```
configs/
├── default.yaml    # Base configuration (always loaded)
├── dev.yaml        # Development overrides
└── prod.yaml       # Production overrides
```

## Loading Configuration

### In Python Code

```python
from ccpp.config import load_config

# Load default config
config = load_config()

# Load environment-specific config
config = load_config(environment="dev")  # Merges default.yaml + dev.yaml
config = load_config(environment="prod")

# Load with runtime overrides
config = load_config(
    environment="dev",
    overrides={"stage1": {"model_name": "qwen3:4b"}}
)

# Access config values
print(config.stage1.backend)  # Dot notation
print(config["stage1"]["backend"])  # Dict notation
```

### Via Environment Variable

Set `CCPP_ENV` to automatically load environment-specific config:

```bash
export CCPP_ENV=dev
python scripts/demo_guard.py  # Automatically uses dev.yaml

export CCPP_ENV=prod
python scripts/demo_guard.py  # Automatically uses prod.yaml
```

### Using with Components

```python
from ccpp.config import load_config, get_stage1_config, get_stage2_config
from ccpp.infer.stage1_router import Stage1Router
from ccpp.infer.stage2_redactor import Stage2Redactor

# Load config
config = load_config(environment="dev")

# Create components with config
router = Stage1Router(
    llm_config=get_stage1_config(config),
    mock_mode=False
)

redactor = Stage2Redactor(
    llm_config=get_stage2_config(config),
    mock_mode=False
)
```

## Configuration Structure

### Stage 1: Fast Risk Router

```yaml
stage1:
  backend: ollama              # Backend: "ollama", "anthropic", "openai"
  model_name: qwen3:1.7b       # Model identifier
  timeout: 60                  # Request timeout (seconds)
  temperature: 0.0             # Sampling temperature (0 = deterministic)
  max_tokens: 5                # Max tokens to generate
  token_a: SAFE                # Token for safe classification
  token_b: RISK                # Token for risk classification
  system_prompt: "..."         # Optional system prompt
  few_shot_examples: []        # Optional few-shot examples
```

### Stage 2: Entity Redactor

```yaml
stage2:
  backend: ollama              # Backend: "ollama", "anthropic", "openai"
  model_name: qwen3:4b         # Model identifier (typically larger)
  timeout: 120                 # Request timeout (seconds)
  temperature: 0.0             # Sampling temperature
  max_tokens: 200              # Max tokens for entity extractions
  system_prompt: "..."         # Optional system prompt
  few_shot_examples: []        # Optional few-shot examples
```

### Streaming Parameters

```yaml
streaming:
  stream_break_timeout_ms: 2000   # Time since last token → trigger masking (2s for voice pauses)
  holdback_buffer_size: 512       # Max buffer size before forcing decision
  overlap_chars: 64               # Chars to retain for cross-utterance detection

  # EMA (Exponential Moving Average) settings
  ema_beta: 0.85                  # Smoothing factor (0.8-0.9)
  reset_ema_on_stream_break: false  # Reset EMA at breaks?

  # Hysteresis thresholds
  t_high: 0.6                     # EMA threshold to escalate to Stage 2
  t_low: 0.3                      # EMA threshold to de-escalate
  risk_threshold: 0.7             # Individual token P(RISK) threshold
```

### Heuristics (Pre-Stage-1 Patterns)

```yaml
heuristics:
  enabled: true                   # Enable fast regex detection
  strong_match_confidence: 0.9    # Confidence for direct Stage 2 escalation

  patterns:
    email:
      enabled: true
      confidence: 1.0
    phone:
      enabled: true
      confidence: 0.95
    # ... more patterns
```

### Masking Output

```yaml
masking:
  default_format: "[{category}]"   # Default mask format

  category_formats:                 # Category-specific formats
    pii/direct: "[PII/DIRECT]"
    credentials: "[CREDENTIALS]"
    financial: "[FINANCIAL]"

  case_sensitive: true              # Match entities case-sensitively
```

## Environment-Specific Overrides

### Development (`dev.yaml`)

Optimized for local development:

```yaml
stage1:
  backend: ollama
  model_name: qwen3:1.7b
  timeout: 30                      # Faster timeout for dev

streaming:
  stream_break_timeout_ms: 300     # Faster breaks for testing

logging:
  level: DEBUG                     # Verbose logging
```

### Production (`prod.yaml`)

Optimized for production with cloud APIs:

```yaml
stage1:
  backend: anthropic
  model_name: claude-haiku-4-5-20251001   # Fast, low-cost

stage2:
  backend: anthropic
  model_name: claude-sonnet-4-5-20250929  # Accurate, higher-cost

logging:
  level: INFO                      # Production logging
```

## Runtime Overrides via Environment Variables

Override any config value using environment variables with the `CCPP_` prefix:

```bash
# Override Stage 1 backend
export CCPP_STAGE1__BACKEND=anthropic
export CCPP_STAGE1__MODEL_NAME=claude-haiku-4-5-20251001

# Override streaming timeout
export CCPP_STREAMING__STREAM_BREAK_TIMEOUT_MS=300

# Override thresholds
export CCPP_STREAMING__T_HIGH=0.7
export CCPP_STREAMING__EMA_BETA=0.9

# Run with overrides
python scripts/demo_guard.py
```

**Syntax**: `CCPP_<section>__<key>=<value>`
- Sections and keys are lowercase
- Use double underscores (`__`) for nesting
- Values are auto-parsed as int, float, bool, or string

## Common Configuration Patterns

### Local Development (Ollama)

```yaml
# configs/dev.yaml
stage1:
  backend: ollama
  model_name: qwen3:1.7b
  timeout: 30

stage2:
  backend: ollama
  model_name: qwen3:4b
  timeout: 60
```

### Production (Cloud APIs)

```yaml
# configs/prod.yaml
stage1:
  backend: anthropic
  model_name: claude-haiku-4-5-20251001   # Fast Haiku for Stage 1

stage2:
  backend: anthropic
  model_name: claude-sonnet-4-5-20250929  # Accurate Sonnet for Stage 2
```

### Hybrid (Local Stage 1, Cloud Stage 2)

```yaml
# configs/hybrid.yaml
stage1:
  backend: ollama
  model_name: qwen3:1.7b            # Fast local classification

stage2:
  backend: anthropic
  model_name: claude-sonnet-4-5-20250929  # Accurate cloud redaction
```

### Aggressive PII Detection

```yaml
# configs/aggressive.yaml
streaming:
  t_high: 0.4                       # Lower threshold (more sensitive)
  t_low: 0.2
  risk_threshold: 0.5               # Lower risk threshold

heuristics:
  strong_match_confidence: 0.8      # Lower confidence for escalation
```

### Conservative PII Detection

```yaml
# configs/conservative.yaml
streaming:
  t_high: 0.8                       # Higher threshold (less sensitive)
  t_low: 0.5
  risk_threshold: 0.85

heuristics:
  enabled: false                    # Disable fast heuristics (model-only)
```

### Voice Conversation Tuning

The default config is optimized for real-time voice conversations. Here are patterns for different voice scenarios:

#### Fast Speakers / Short Pauses

```yaml
# configs/fast_speech.yaml
streaming:
  stream_break_timeout_ms: 1000    # 1s timeout for rapid speakers
  holdback_buffer_size: 256        # Smaller buffer
```

**Use case:** When users speak quickly with minimal pauses (presentations, podcasts)

#### Slow Speakers / Long Pauses

```yaml
# configs/slow_speech.yaml
streaming:
  stream_break_timeout_ms: 3000    # 3s timeout for thoughtful speakers
  holdback_buffer_size: 768        # Larger buffer for longer utterances
```

**Use case:** When users pause frequently to think (interviews, technical discussions)

#### Noisy Environments / Frequent Interruptions

```yaml
# configs/noisy.yaml
streaming:
  stream_break_timeout_ms: 1500    # Medium timeout
  overlap_chars: 128               # Larger overlap for interrupted speech

heuristics:
  strong_match_confidence: 0.95    # Higher confidence to reduce false positives
```

**Use case:** Call centers, public spaces, multi-speaker conversations

#### Voice Assistant / Interactive

```yaml
# configs/assistant.yaml
streaming:
  stream_break_timeout_ms: 1500    # Responsive but not too aggressive
  t_high: 0.5                      # Lower threshold for higher sensitivity
  ema_beta: 0.8                    # Less smoothing for faster reaction
```

**Use case:** Voice assistants, chatbots, interactive systems where latency matters

**Tuning guidelines:**

| Scenario | Timeout | Buffer Size | Threshold | Why |
|----------|---------|-------------|-----------|-----|
| Fast speech | 1000ms | 256 | 0.6 (default) | Quick decisions for rapid speakers |
| Normal (default) | 2000ms | 512 | 0.6 | Handles typical voice pauses |
| Slow speech | 3000ms | 768 | 0.6 | Accommodates thinking pauses |
| High noise | 1500ms | 512 | 0.7 | Faster decisions, higher confidence |
| Low latency | 1000ms | 256 | 0.5 | Quick response, more sensitive |

## Customizing Configs

### Create Custom Environment

```yaml
# configs/staging.yaml
# Inherits from default.yaml, overrides for staging

stage1:
  backend: anthropic
  model_name: claude-haiku-4-5-20251001
  timeout: 15

logging:
  level: INFO
```

Load it:
```python
config = load_config(environment="staging")
```

Or:
```bash
export CCPP_ENV=staging
python scripts/demo_guard.py
```

### Create User-Specific Config

```yaml
# configs/myconfig.yaml
stage1:
  backend: ollama
  model_name: qwen3:4b   # Use larger model for better accuracy

streaming:
  stream_break_timeout_ms: 1000   # Longer timeout for slower typing
```

Load it:
```python
config = load_config(config_path="configs/myconfig.yaml")
```

## Best Practices

### 1. Use Environment-Specific Configs

✅ **Good**: Separate configs for each environment
```
configs/dev.yaml    # Local development
configs/prod.yaml   # Production
```

❌ **Bad**: Hardcoded values in code
```python
backend = OllamaBackend(model_name="qwen3:1.7b")  # Hardcoded!
```

### 2. Extend, Don't Replace

✅ **Good**: Override only what changes
```yaml
# prod.yaml - only overrides
stage1:
  backend: anthropic
```

❌ **Bad**: Duplicate entire config
```yaml
# prod.yaml - duplicates everything from default.yaml
stage1:
  backend: anthropic
  model_name: ...
  timeout: ...
  # ... all other fields
```

### 3. Use Environment Variables for Secrets

✅ **Good**: API keys from environment
```yaml
# Config file (no secrets)
stage1:
  backend: anthropic
  # API key from ANTHROPIC_API_KEY env var
```

❌ **Bad**: API keys in config file
```yaml
stage1:
  backend: anthropic
  api_key: sk-ant-...  # DON'T DO THIS!
```

### 4. Document Custom Configs

```yaml
# configs/custom.yaml
# Custom configuration for [purpose]
# Author: [name]
# Date: [date]

stage1:
  # Use larger model for better accuracy in [scenario]
  model_name: qwen3:4b
```

## Validation

Config values are validated at load time:

```python
try:
    config = load_config()
except FileNotFoundError:
    print("Config file not found")
except yaml.YAMLError:
    print("Invalid YAML syntax")
```

Component initialization validates required fields:

```python
try:
    router = Stage1Router(llm_config=get_stage1_config(config))
except ValueError as e:
    print(f"Invalid config: {e}")
```

## Example: Complete Configuration Flow

```python
# Load environment-specific config
config = load_config(environment="prod")

# Apply runtime overrides if needed
if use_local_stage1:
    config = load_config(
        environment="prod",
        overrides={"stage1": {"backend": "ollama"}}
    )

# Extract component configs
stage1_config = get_stage1_config(config)
stage2_config = get_stage2_config(config)

# Initialize components
router = Stage1Router(llm_config=stage1_config, mock_mode=False)
redactor = Stage2Redactor(llm_config=stage2_config, mock_mode=False)

# Access streaming params
timeout = config.streaming.stream_break_timeout_ms
t_high = config.streaming.t_high
```

## Troubleshooting

### "Config file not found"
- Ensure `configs/default.yaml` exists
- Check working directory: `pwd`
- Use absolute path: `load_config(config_path="/full/path/to/config.yaml")`

### "Invalid YAML syntax"
- Validate YAML: `python -c "import yaml; yaml.safe_load(open('configs/default.yaml'))"`
- Check indentation (YAML is whitespace-sensitive)

### Environment overrides not working
- Check env var name: `echo $CCPP_STAGE1__BACKEND`
- Use correct format: `CCPP_<SECTION>__<KEY>` (double underscores)
- Restart process after setting env vars
