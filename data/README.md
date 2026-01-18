# Data Directory

Training data generation for PII detection models.

## Directory Structure

```
data/
├── scripts/            # Data generation pipeline
│   ├── generator.py    # LLM conversation generation
│   ├── formatter.py    # Stage 1 training format
│   ├── stage2_formatter.py  # Stage 2 training format
│   ├── main.py         # CLI orchestrator
│   └── test_generator.py    # Test script with debugging
├── constitutions/      # PII definitions for training data
│   ├── pii_harmful.md  # What counts as PII
│   ├── pii_harmless.md # What doesn't count as PII
│   └── prompt_template.md   # Classifier prompt templates
├── synthetic/          # Raw generated conversations (JSONL)
├── training/           # Formatted training data
│   ├── stage1.jsonl    # Speculative classification examples
│   └── stage2.jsonl    # Entity extraction examples
└── test_output/        # Test script output (gitignored)
```

## Quick Start

```bash
# Generate test conversations with full debugging output
uv run python -m data.scripts.test_generator --count 5 --output-dir data/test_output

# Generate sample conversations for validation
uv run python -m data.scripts.main sample --count 50

# Generate full dataset + format for training
uv run python -m data.scripts.main all --count 1000
```

## Pipeline Stages

### 1. Generate Synthetic Conversations

Uses Claude Haiku to generate realistic voice/phone customer support conversations with labeled PII entities.

**Output format** (`synthetic/raw_conversations.jsonl`):
```json
{
  "conversation_id": "conv_abc123",
  "messages": [
    {
      "role": "user",
      "content": "My email is john at gmail dot com",
      "content_redacted": "My email is [EMAIL]",
      "pii_entities": [{"text": "john at gmail dot com", "category": "contact"}]
    }
  ],
  "has_pii": true,
  "pii_categories_present": ["contact"]
}
```

### 2. Format for Stage 1 (Speculative Classification)

Creates training examples for the fast risk router. Each user message generates multiple prefix examples - all prefixes share the same label as the full message.

**Output format** (`training/stage1.jsonl`):
```json
{
  "context": [{"role": "assistant", "content": "How can I help?"}],
  "buffer": "My email is john",
  "label": "FAIL",
  "category": "contact",
  "prefix_end": 16,
  "is_full": false
}
```

### 3. Format for Stage 2 (Entity Extraction)

Creates training examples for the entity redactor. Only processes user messages.

**Output format** (`training/stage2.jsonl`):
```json
{
  "context": [{"role": "assistant", "content": "What's your email?"}],
  "window_text": "It's john at gmail dot com",
  "target_output": "MASK \"john at gmail dot com\" contact"
}
```

## Test Script

The test script generates conversations and shows the full pipeline:

```bash
uv run python -m data.scripts.test_generator --count 3 --output-dir data/test_output
```

**Output files:**
- `conversations_*.jsonl` - Raw generated conversations
- `api_calls_*.json` - Full prompt/response pairs from Claude API
- `stage1_examples_*.jsonl` - Formatted Stage 1 training data
- `stage2_examples_*.jsonl` - Formatted Stage 2 training data
- `summary_*.txt` - Human-readable summary with examples

**Options:**
- `--count N` - Number of conversations to generate
- `--pii` / `--no-pii` - Force PII inclusion/exclusion
- `--category TYPE` - Force specific PII category
- `--verbose` - Enable debug logging
