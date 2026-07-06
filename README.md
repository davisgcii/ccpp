# CC++ PII Masking

Streaming PII detection and masking, adapted from Anthropic's [Constitutional Classifiers](https://arxiv.org/abs/2501.18837) / [CC++](https://arxiv.org/abs/2601.04603) jailbreak detection papers. Uses a two-stage cascade of fine-tuned small models (Qwen3-0.6B + 1.7B) to classify and redact PII in real time as text streams in.

## Quick Start

```bash
git clone https://github.com/davisgcii/ccpp.git
cd ccpp
./setup.sh                                # installs deps, prompts for API key
uv run python scripts/nicegui_client.py   # launches demo GUI at http://127.0.0.1:8080
```

Default backend is **MLX** (Apple Silicon). For cross-platform support, use [Ollama](#configuration). Base models download automatically on first run; pre-trained LoRA adapters are included.

> **About the demo:** the GUI redacts the text *you type* — a stand-in for a live transcribed-speech stream — and runs the masking decision when you hit **Send**. In a real deployment the same cascade would run continuously on an incoming stream.

## Overview

The CC++ papers introduce a streaming two-stage cascade for jailbreak detection: a cheap, fast classifier scores every chunk of model output, and an expensive, precise model only activates when risk is flagged. This keeps false positives low and inference overhead small.

This project applies the same architecture to **PII masking** instead — the same streaming cascade redacts PII from a text stream (rather than blocking harmful model output). A key addition is _speculative classification_ — the Stage 1 model is trained on prefixes of PII-containing messages, so it can flag risk before PII is fully present (e.g., "my email is" triggers before the address appears). This helps in streaming/voice contexts where PII arrives incrementally or is split across utterances.

## Architecture

Two-stage cascade with fast heuristics:

1. **Stage 1 — Classifier** (Qwen3-0.6B): Runs on each chunk as text streams in, producing a calibrated P(FAIL) risk score. Scores are EMA-smoothed to reduce noise.
2. **Stage 2 — Redactor** (Qwen3-1.7B): Invoked only when the stream pauses _and_ risk was detected. Extracts and classifies PII entities.
3. **Heuristics**: Regex patterns (email, phone, SSN, credit card, API keys) for instant high-confidence detection.

```
Streaming text
      │
      ▼
  ┌──────────────────────────────────┐
  │  On each chunk:                  │
  │                                  │
  │  Regex heuristics → instant flag │
  │  Stage 1 classifier → P(FAIL)    │
  │  EMA smoothing (β=0.85)          │
  └───────────────┬──────────────────┘
                  │
             Stream pauses
                  │
                  ▼
          ┌───────────────┐
          │  Trigger?     │
          │  • risk ≥ 0.7 │
          │  • ema  ≥ 0.4 │
          │  • heuristic  │
          └──┬─────────┬──┘
          no │         │ yes
             ▼         ▼
          Pass      Stage 2 redactor
          through   → MASK "entity" category
```

## PII Categories

| Category    | Examples                                       |
| ----------- | ---------------------------------------------- |
| person      | Human names                                    |
| contact     | Email, phone numbers                           |
| gov_id      | SSN, driver's license, passport, date of birth |
| identifier  | Order numbers, account IDs, tracking numbers   |
| location    | Street addresses, coordinates                  |
| financial   | Credit cards, bank accounts                    |
| credentials | Passwords, API keys, tokens                    |
| medical     | Medical record numbers, diagnoses              |

## Configuration

All settings in `configs/default.yaml`.

| Setting                      | Default                         | Description                                        |
| ---------------------------- | ------------------------------- | -------------------------------------------------- |
| `stage1.backend`             | `mlx`                           | `mlx` (Apple Silicon) or `ollama` (cross-platform) |
| `stage1.model_name`          | `mlx-community/Qwen3-0.6B-4bit` | Stage 1 classifier model                           |
| `stage2.model_name`          | `Qwen/Qwen3-1.7B-MLX-8bit`      | Stage 2 redactor model                             |
| `streaming.t_high` / `t_low` | `0.4` / `0.2`                   | EMA hysteresis thresholds                          |
| `streaming.risk_threshold`   | `0.7`                           | Per-chunk risk threshold                           |

For **Ollama**: set `backend: ollama`, use `qwen3:0.6b` / `qwen3:1.7b`, set `sequence_loglikelihood.enabled: false`.

## Training

Pre-trained LoRA adapters are included. To retrain from scratch:

```bash
# 1. Generate synthetic conversations (requires ANTHROPIC_API_KEY)
uv run python -m data.scripts.main all --count 1000

# 2. Convert to MLX training format
uv run python -m data.scripts.convert_to_mlx --stage 1
uv run python -m data.scripts.convert_to_mlx --stage 2

# 3. Train LoRA adapters
uv run python -m mlx_lm.lora --config configs/lora_stage1.yaml
uv run python -m mlx_lm.lora --config configs/lora_stage2.yaml
```

See `data/README.md` for data format details and `CLAUDE.md` for the full training + evaluation workflow.

## Testing

```bash
uv run pytest                    # unit tests
uv run pytest -m integration     # integration tests (requires Ollama or API keys)
```

## Project Structure

```
src/ccpp/
  infer/       Stage 1 router, Stage 2 redactor, heuristics, guard pipeline
  llm/         LLM backends (MLX, Ollama, Anthropic, OpenAI)
  nicegui/     Demo GUI
  types.py     Core data types
  config.py    Configuration
configs/       YAML configuration
data/          Synthetic data generation + training pipeline
models/        LoRA adapter weights
tests/         Test suite
```

## References

- [Constitutional Classifiers](https://arxiv.org/abs/2501.18837) — Anthropic, arXiv
- [Constitutional Classifiers++](https://arxiv.org/abs/2601.04603) — Anthropic, arXiv
- [Anthropic blog: Constitutional Classifiers](https://www.anthropic.com/research/constitutional-classifiers)
- [Anthropic blog: Next-Gen Constitutional Classifiers](https://www.anthropic.com/research/next-generation-constitutional-classifiers)
