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
- **Backend**: Ollama (default) or MLX (Apple Silicon)
- **Model**: qwen3:0.6b (fast) or qwen3:1.7b (more accurate)
- **Method**: Native logprobs API with `think=False` to disable Qwen3 thinking mode
- **Output**: Calibrated probability P(FAIL) ∈ [0,1] from softmax over SAFE/FAIL logprobs
- **Speed**: ~300-500ms per classification (Ollama), ~10-20ms (MLX sequence LL)

### Stage 2: Entity Redactor
- **Backend**: Ollama (default) or MLX (Apple Silicon)
- **Model**: qwen3:1.7b (more accurate for entity extraction)
- **Output**: `PASS` or `MASK "entity" category; ...`
- **Invoked**: Only at stream breaks when risk detected

### Risk Management
- **EMA Smoothing**: `ema = 0.85 * ema + 0.15 * risk`
- **Hysteresis**: T_high=0.6 (escalate), T_low=0.3 (de-escalate)
- **Three conditions**: Mask if `any_risk_in_buffer` OR `ema ≥ T_high` OR `strong_heuristic_match`

## Label Schema

| Category | Description |
|----------|-------------|
| safe | No PII |
| pii/direct | Email, phone, SSN, name+DOB combos |
| pii/indirect | Quasi-identifiers enabling re-identification |
| credentials | API keys, passwords, tokens |
| financial | Account/card numbers, tax IDs |
| medical | Diagnoses, prescriptions, record numbers |
| location/precise | Exact addresses, coordinates |

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
MASK "john.doe@gmail.com" pii/direct
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
configs/
└── default.yaml     # Default configuration (MLX backend)
tests/               # Test suite
docs/                # Additional documentation
constitutions/       # PII definitions and allowlists
```

## Configuration

Single config file: `configs/default.yaml`

Key settings:
- `stage1.backend: ollama` - Use Ollama with native logprobs (default)
- `stage1.model_name: qwen3:0.6b` - Fast model for Stage 1
- `stage2.model_name: qwen3:1.7b` - Larger model for Stage 2
- `streaming.stream_break_timeout_ms: 2000` - 2s timeout for voice pauses
- `streaming.t_high: 0.6` - EMA threshold to escalate
- `streaming.risk_threshold: 0.7` - Individual token threshold

**Note**: Prompt templates use `Answer:` ending (not `Classification:`) to prevent model from echoing the word.

## Development Notes

- Use `uv` for all Python commands (not pip/conda)
- GUI is the primary interface: `scripts/gui_client.py`
- Logs available at `/tmp/gui_debug.log` and `/tmp/prompt_logs.jsonl`
- All 131 tests should pass: `uv run pytest`

## Reference
- `TODO.md` - Progress tracking and next steps
- `papers/Constitutional Classifiers++.pdf` - Primary paper
