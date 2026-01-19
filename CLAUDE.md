# CLAUDE.md

Guidance for coding agents working in this repository.

**Important**: Qwen3 is the latest Qwen model (not 2.5). Similarly, gpt-5-mini and claude-haiku-4-5-20251001 are the most up-to-date OpenAI and Anthropic models.

## Quick Start

```bash
uv sync                              # Install dependencies
uv run python scripts/gui_client.py  # Launch GUI (http://127.0.0.1:7860)
uv run pytest                        # Run tests
```

## Project Intent

This repo implements a **CC++-inspired streaming exchange classifier** for PII detection and masking in black-box hosted LLMs. We are **not** building jailbreak refusal - we are building **PII/sensitive-info detection + masking (redaction)** in streaming outputs.

Key mechanics from CC++:
- **Exchange-aware** evaluation (judge current chunk in context of prior conversation)
- **Streaming** evaluation (score in batches during generation)
- **Two-stage cascade** (cheap high-recall router → expensive accurate redactor)
- **Calibration** to control false positives

## Architecture

```
Streaming text → HoldbackBuffer → Fast Heuristics → Stage 1 Router → EMA Smoothing
                                        ↓                   ↓
                              (strong match?)        (risk ≥ 0.7?)
                                        ↓                   ↓
                                   ←←←←←←←←←←←←←←←←←←←←←←←
                                              ↓
                              Stream break? (timeout ≥ 2s)
                                              ↓ Yes
                              Masking decision (any_risk OR ema≥T_high OR strong_match)
                                              ↓ Yes
                                     Stage 2: Entity Redactor
                                              ↓
                                     Apply masks → Emit text
```

### Stage 1: Fast Risk Router
- **Backend**: MLX (default, Apple Silicon) or Ollama (cross-platform)
- **Model**: mlx-community/Qwen3-0.6B-4bit (MLX) or qwen3:0.6b (Ollama)
- **Method**: Sequence log-likelihood (MLX) or native logprobs API (Ollama)
- **Output**: Calibrated probability P(FAIL) ∈ [0,1]
- **Speed**: ~2-2.5s per classification (MLX with 0.6B-4bit), ~300-500ms (Ollama)
- **Note**: Classifications are queued and processed by timer, not blocking keystrokes

### Stage 2: Entity Redactor
- **Backend**: MLX (default, Apple Silicon) or Ollama (cross-platform)
- **Model**: Qwen/Qwen3-1.7B-MLX-8bit (MLX) or qwen3:1.7b (Ollama)
- **Output**: `PASS` or `MASK "entity" category; ...`
- **Invoked**: Only at stream breaks when risk detected

### Risk Management
- **EMA Smoothing**: `ema = 0.85 * ema + 0.15 * risk`
- **Hysteresis**: T_high=0.4 (escalate), T_low=0.2 (de-escalate)
- **Three conditions**: Mask if `any_risk_in_buffer` OR `ema ≥ T_high` OR `strong_heuristic_match`

## Label Schema

| Category | Description |
|----------|-------------|
| safe | No PII |
| person | Human names (first, last, full) |
| contact | Email addresses, phone numbers |
| gov_id | SSN, driver's license, passport, date of birth |
| identifier | Order numbers, account IDs, tracking numbers |
| location | Physical addresses, coordinates |
| financial | Credit cards, bank accounts, routing numbers |
| credentials | Passwords, API keys, tokens |
| medical | Medical record numbers, diagnoses, prescriptions |

## Key Implementation Details

### Tokens: SAFE/FAIL (not RISK)
"RISK" tokenizes to multiple tokens ["R", "ISK"] in Qwen3. We use "FAIL" which is a single token.

### Buffer-Scoped Labels (Critical for Training)
Labels apply to **current buffer only**, not entire exchange:
- Historical PII in context → label = SAFE
- PII in current buffer → label = FAIL

### Stage 2 Output Format
```
PASS
MASK "john.doe@gmail.com" contact
MASK "entity1" cat1; MASK "entity2" cat2
```
Uses entity text (not character offsets) because LLMs are bad at counting.

## Repo Structure

```
src/ccpp/
├── infer/           # Inference pipeline (guard, stage1_router, stage2_redactor, heuristics)
├── llm/             # LLM backends (MLX, Ollama, Anthropic, OpenAI)
├── gui/             # GUI client (state, components, app)
├── types.py         # Core data types
└── config.py        # Configuration system
scripts/
└── gui_client.py    # Interactive GUI client
data/
├── scripts/         # Training data generation pipeline
├── constitutions/   # PII definitions for training data
├── synthetic/       # Raw generated conversations
├── training/        # Formatted training data (stage1, stage2)
└── test_output/     # Test script output (gitignored)
configs/
└── default.yaml     # Default configuration (MLX backend)
tests/               # Test suite
docs/                # Additional documentation
constitutions/       # PII definitions for inference
```

## Configuration

Single config file: `configs/default.yaml`

Key settings:
- `stage1.backend: mlx` - Use MLX with sequence log-likelihood (default)
- `stage1.model_name: mlx-community/Qwen3-0.6B-4bit` - Fast MLX model for Stage 1
- `stage2.model_name: Qwen/Qwen3-1.7B-MLX-8bit` - Accurate MLX model for Stage 2
- `stage1.sequence_loglikelihood.enabled: true` - Required for MLX backend
- `streaming.stream_break_timeout_ms: 2000` - 2s timeout for voice pauses
- `streaming.t_high: 0.4` - EMA threshold to escalate
- `streaming.t_low: 0.2` - EMA threshold to de-escalate
- `streaming.risk_threshold: 0.7` - Individual token threshold

**Note**: For Ollama backend, set `backend: ollama`, use `qwen3:0.6b`/`qwen3:1.7b` models, and set `sequence_loglikelihood.enabled: false`. Prompt templates use `Answer:` ending to prevent model echo.

## Development Notes

- Use `uv` for all Python commands (not pip/conda)
- GUI is the primary interface: `scripts/gui_client.py`
- Logs available at `/tmp/gui_debug.log` and `/tmp/prompt_logs.jsonl`
- All 131 tests should pass: `uv run pytest`

## Dataset Generation

Generate synthetic training data for PII classification models.

```bash
# Test the pipeline (generates conversations + shows formatted training examples)
uv run python -m data.scripts.test_generator --count 5 --output-dir data/test_output

# Generate sample conversations for validation
uv run python -m data.scripts.main sample --count 50

# Full pipeline: generate + format + split
uv run python -m data.scripts.main all --count 1000
```

**Pipeline stages:**
1. **Generate** - Claude Haiku creates voice/phone conversations with labeled PII
2. **Format Stage 1** - Creates speculative classification examples (prefix training)
3. **Format Stage 2** - Creates entity extraction examples (`MASK "entity" category`)
4. **Split** - Creates train/val splits

See `data/README.md` for detailed format documentation.

## Training Pipeline

Fine-tune Qwen3 models with LoRA adapters using mlx-lm.

### Quick Pipeline Test

```bash
# End-to-end test (generates 1-2 conversations, formats, runs forward pass)
uv run python -m data.scripts.test_pipeline --quick
uv run python -m data.scripts.test_pipeline --count 3 --output-dir data/test_output
```

### Full Training Workflow

```bash
# 1. Generate training data (20+ for testing, 1000+ for real training)
uv run python -m data.scripts.main all --count 100

# 2. Convert to mlx-lm format
uv run python -m data.scripts.convert_to_mlx --stage 1
uv run python -m data.scripts.convert_to_mlx --stage 2

# 3. Evaluate base models (before training)
uv run python -m data.scripts.evaluate --all --output results/baseline.json

# 4. Train LoRA adapters
uv run python -m mlx_lm.lora --config configs/lora_stage1.yaml
uv run python -m mlx_lm.lora --config configs/lora_stage2.yaml

# 5. Evaluate fine-tuned models
uv run python -m data.scripts.evaluate --all \
    --stage1-adapter models/adapters/stage1/qwen3-0.6b-pii-classifier \
    --stage2-adapter models/adapters/stage2/qwen3-1.7b-pii-redactor \
    --output results/finetuned.json

# 6. Compare results
uv run python -m data.scripts.evaluate --compare results/baseline.json results/finetuned.json

# 7. Enable adapters in configs/default.yaml:
#    stage1.adapter_path: models/adapters/stage1/qwen3-0.6b-pii-classifier
#    stage2.adapter_path: models/adapters/stage2/qwen3-1.7b-pii-redactor
```

### Adapters

After training, adapters are stored in:
- `models/adapters/stage1/qwen3-0.6b-pii-classifier/`
- `models/adapters/stage2/qwen3-1.7b-pii-redactor/`

Enable by setting `adapter_path` in `configs/default.yaml`.

## Reference
- `TODO.md` - Progress tracking and next steps
- `papers/Constitutional Classifiers++.pdf` - Primary paper
