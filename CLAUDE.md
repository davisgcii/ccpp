# CLAUDE.md

Guidance for coding agents working in this repository.

**Important**: Qwen3 is the latest Qwen model (not 2.5). Similarly, gpt-5-mini and claude-haiku-4-5-20251001 are the most up-to-date OpenAI and Anthropic models.

## Quick Start

```bash
uv sync                                    # Install dependencies
uv run python scripts/nicegui_client.py    # Launch GUI (http://127.0.0.1:8080)
uv run pytest                              # Run tests (132 tests)
```

## Project Intent

This repo implements a **CC++-inspired streaming exchange classifier** for PII detection and masking. We are **not** building jailbreak refusal — we are building **PII detection + masking (redaction)** in streaming outputs.

See `README.md` for a high-level overview of the architecture and the CC++ papers it's based on.

## Repo Structure

```
src/ccpp/
├── infer/           # Inference pipeline
│   ├── guard.py     #   Orchestrator: buffer → heuristics → stage1 → stage2 → mask
│   ├── heuristics.py#   Regex patterns (email, phone, SSN, credit card, API keys)
│   ├── stage1_router.py    # Fast SAFE/FAIL classifier
│   └── stage2_redactor.py  # Entity extraction + masking
├── llm/             # LLM backends
│   ├── base.py      #   Backend protocol + shared types
│   ├── factory.py   #   create_backend_from_config()
│   ├── mlx_backend.py      # MLX (Apple Silicon, sequence log-likelihood)
│   ├── ollama_backend.py   # Ollama (cross-platform, logprobs API)
│   ├── api_backend.py      # Anthropic + OpenAI (AnthropicBackend, OpenAIBackend)
│   └── prompt_logger.py    # Logs prompts to /tmp/prompt_logs.jsonl
├── nicegui/         # NiceGUI demo client (app, components, styles)
├── gui/             # Gradio client (legacy, not actively maintained)
├── types.py         # Core data types
├── config.py        # Configuration system (loads configs/default.yaml)
└── logging_config.py
scripts/
├── nicegui_client.py # NiceGUI launcher (primary)
└── gui_client.py     # Gradio launcher (legacy)
data/
├── scripts/         # Training data generation pipeline
│   ├── main.py      #   CLI: sample, generate, format, split, all
│   ├── generator.py #   LLM conversation generation (Claude Haiku)
│   ├── formatter.py #   Stage 1 training format (prefix examples)
│   ├── stage2_formatter.py  # Stage 2 training format (entity extraction)
│   ├── convert_to_mlx.py    # Convert to mlx-lm JSONL format
│   ├── evaluate.py  #   Model evaluation + comparison
│   ├── test_generator.py    # Test script with debugging output
│   └── test_pipeline.py     # End-to-end pipeline test
├── constitutions/   # PII definitions for training data
├── synthetic/       # Raw generated conversations (JSONL)
└── training/        # Formatted training data (stage1.jsonl, stage2.jsonl)
configs/
├── default.yaml     # Runtime configuration
├── lora_stage1.yaml # Stage 1 LoRA training config
└── lora_stage2.yaml # Stage 2 LoRA training config
models/adapters/     # LoRA adapter weights (stage1 + stage2)
constitutions/       # PII definitions for inference prompts
tests/               # 132 unit tests + integration tests
docs/                # CONFIG.md, TESTING.md, stream.md
```

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

### Risk Management
- **EMA Smoothing**: `ema = 0.85 * ema + 0.15 * risk`
- **Hysteresis**: T_high=0.4 (escalate), T_low=0.2 (de-escalate)
- **Three triggers**: Mask if `any_risk_in_buffer` (≥ 0.7) OR `ema ≥ T_high` OR `strong_heuristic_match`

### Label Schema

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

## Configuration

Single config file: `configs/default.yaml`

Key settings:
- `stage1.backend: mlx` — MLX with sequence log-likelihood (default)
- `stage1.model_name: mlx-community/Qwen3-0.6B-4bit` — Fast model for Stage 1
- `stage2.model_name: Qwen/Qwen3-1.7B-MLX-8bit` — Accurate model for Stage 2
- `stage1.sequence_loglikelihood.enabled: true` — Required for MLX backend
- `streaming.stream_break_timeout_ms: 2000` — 2s pause triggers masking decision
- `streaming.t_high: 0.4` / `t_low: 0.2` — EMA hysteresis thresholds
- `streaming.risk_threshold: 0.7` — Individual chunk risk threshold

For Ollama: set `backend: ollama`, use `qwen3:0.6b`/`qwen3:1.7b`, set `sequence_loglikelihood.enabled: false`. Prompt templates use `Answer:` ending to prevent model echo.

## Development Notes

- Use `uv` for all Python commands (not pip/conda)
- Logs: `/tmp/gui_debug.log` and `/tmp/prompt_logs.jsonl`
- All 132 tests should pass: `uv run pytest`

## Dataset Generation

```bash
# Test the pipeline
uv run python -m data.scripts.test_generator --count 5 --output-dir data/test_output

# Generate sample conversations
uv run python -m data.scripts.main sample --count 50

# Full pipeline: generate + format + split
uv run python -m data.scripts.main all --count 1000
```

Pipeline stages:
1. **Generate** — Claude Haiku creates voice/phone conversations with labeled PII
2. **Format Stage 1** — Creates speculative classification examples (prefix training)
3. **Format Stage 2** — Creates entity extraction examples (`MASK "entity" category`)
4. **Split** — Creates train/val splits

See `data/README.md` for detailed format documentation.

## Training Pipeline

```bash
# Quick end-to-end test
uv run python -m data.scripts.test_pipeline --quick

# Full workflow
uv run python -m data.scripts.main all --count 1000
uv run python -m data.scripts.convert_to_mlx --stage 1
uv run python -m data.scripts.convert_to_mlx --stage 2
uv run python -m data.scripts.evaluate --all --output results/baseline.json
uv run python -m mlx_lm.lora --config configs/lora_stage1.yaml
uv run python -m mlx_lm.lora --config configs/lora_stage2.yaml
uv run python -m data.scripts.evaluate --all \
    --stage1-adapter models/adapters/stage1/qwen3-0.6b-pii-classifier \
    --stage2-adapter models/adapters/stage2/qwen3-1.7b-pii-redactor \
    --output results/finetuned.json
uv run python -m data.scripts.evaluate --compare results/baseline.json results/finetuned.json
```

Adapters are stored in `models/adapters/stage{1,2}/`. Enable by setting `adapter_path` in `configs/default.yaml`.

## Reference
- `README.md` — Project overview and quick start
- `papers/Constitutional Classifiers++.pdf` — Primary paper
