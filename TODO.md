# TODO.md

CC++-inspired streaming PII masker for black-box LLMs.

## Current Status

**Core pipeline is functional** - Stage 1 classification and Stage 2 redaction are working.

### Completed
- MLX backend with sequence log-likelihood (default, Apple Silicon)
- Ollama backend with native logprobs API (cross-platform alternative)
- Two-stage cascade architecture
- Fast heuristics (regex patterns)
- Stream break detection and EMA smoothing
- GUI client with real-time visualization
- Configuration system (YAML)
- 131 unit/integration tests passing
- Prompt templates with `Answer:` ending (prevents model echo)
- Qwen3 `think=False` integration
- Training data generation pipeline (`data/scripts/`)
  - Synthetic conversation generator using Claude Haiku
  - Stage 1 formatter (speculative prefix classification)
  - Stage 2 formatter (entity extraction training)
  - Constitution loader for PII definitions

### Not Started
- Structured outputs for reliable SAFE/FAIL classification
- Model fine-tuning
- Evaluation and calibration

---

## Phase 3: Synthetic Data Generation ✅

**Completed** - Pipeline implemented in `data/scripts/`

### Stage 1 Training Data
Each record needs:
- `messages`: Conversation context (may include historical PII)
- `current_buffer`: Text being classified
- `label`: `SAFE` or `FAIL` (applies to current_buffer only!)
- **Critical**: Historical PII in messages does NOT cause FAIL label

### Stage 2 Training Data
Each record needs:
- `messages`: Conversation context
- `window_text`: Exact redaction window (buffer + overlap tail)
- `entities`: `[{entity_text, category}]`
- `target_output`: `PASS` or `MASK "entity" category`

### Generator Tasks
- [x] Create prompts using placeholders (`<EMAIL>`, `<PHONE>`, `<NAME>`, etc.)
- [x] Hydrate placeholders with synthetic PII (Claude Haiku generates realistic voice conversations)
- [x] Generate buffer-scoped labels for Stage 1 (formatter.py)
- [x] Generate Stage 2 entity extraction training data (stage2_formatter.py)
- [ ] Generate benign "near misses" (example.com, test keys) - needs more examples
- [ ] Output JSONL train/val splits with proper ratio

---

## Phase 4: Data Augmentation

### Basic Augmentations
- [ ] Paraphrase, translate/back-translate
- [ ] Formatting variations (tables, code blocks)
- [ ] Role-play wrappers

### Reconstruction-Style Augmentations
- [x] Split entities across stream breaks: "it's george" + [break] + "@gmail.com"
  - Added SPLIT_ENTITY_RATIO (5% of PII conversations)
  - Instruction appended to PII prompt when triggered
  - Tracked via `has_split_entities` field in conversation metadata
- [ ] Insert separators/unicode within entities
- [ ] "Contact card" formatting

---

## Phase 5: Training

**Framework**: mlx-lm native fine-tuning with LoRA adapters (Apple Silicon optimized)

### Infrastructure ✅
- [x] Create `data/scripts/convert_to_mlx.py` - Convert JSONL to mlx-lm chat format
- [x] Create `data/scripts/test_pipeline.py` - End-to-end pipeline test with forward pass
- [x] Create `configs/lora_stage1.yaml` - Stage 1 LoRA training config
- [x] Create `configs/lora_stage2.yaml` - Stage 2 LoRA training config
- [x] Add `adapter_path` support to `src/ccpp/llm/mlx_backend.py`
- [x] Update `src/ccpp/llm/factory.py` to pass adapter_path
- [x] Update `src/ccpp/config.py` to extract adapter_path
- [x] Add `models/adapters/` to `.gitignore`

### Qwen3 Thinking Token Handling
Qwen3 uses `<think>...</think>` scaffolding for chain-of-thought reasoning:
- **Default behavior**: Model outputs thinking content, then answer
- **With `enable_thinking=False`**: Adds empty `<think>\n\n</think>\n\n` scaffold
- **Training format**: Assistant response is `<think>\n\n</think>\n\nSAFE` (or FAIL)
- **Inference**: Model should output SAFE/FAIL directly after the scaffold

**Key insight**: mlx-lm training applies the chat template, which includes the empty
think scaffold. Training teaches the model to output the label directly without
generating thinking content. The `extract_sequence_probs` method in MLX backend
computes P(SAFE) vs P(FAIL) as full sequences, bypassing generation entirely.

### Stage 1 (Logit-Based Router)
- Model: `mlx-community/Qwen3-0.6B-4bit`
- Output: `models/adapters/stage1/qwen3-0.6b-pii-classifier/`
- [ ] Train Stage 1 adapter with mlx-lm
- [ ] Validate SAFE/FAIL accuracy on held-out test set

### Stage 2 (Entity Redactor)
- Model: `Qwen/Qwen3-1.7B-MLX-8bit`
- Output: `models/adapters/stage2/qwen3-1.7b-pii-redactor/`
- [ ] Train Stage 2 adapter with mlx-lm
- [ ] Validate entity extraction accuracy

### Training Commands
```bash
# Quick pipeline test (1 conversation, no forward pass)
uv run python -m data.scripts.test_pipeline --quick

# Full pipeline test (2 conversations, with forward pass)
uv run python -m data.scripts.test_pipeline --output-dir data/test_output

# Full training workflow
uv run python -m data.scripts.main all --count 1000
uv run python -m data.scripts.convert_to_mlx --stage 1
uv run python -m data.scripts.convert_to_mlx --stage 2
uv run python -m mlx_lm.lora --config configs/lora_stage1.yaml
uv run python -m mlx_lm.lora --config configs/lora_stage2.yaml

# After training, enable adapters in configs/default.yaml:
# stage1.adapter_path: models/adapters/stage1/qwen3-0.6b-pii-classifier
# stage2.adapter_path: models/adapters/stage2/qwen3-1.7b-pii-redactor
```

---

## Phase 6: Evaluation

### Metrics
- [ ] Entity-level precision/recall/F1 (exact and partial match)
- [ ] False positive rate on benign corpora (<0.1% target)
- [ ] Stage 2 escalation rate (~10-20%)
- [ ] Latency: Stage 1 <20ms, Stage 2 <100ms

### Calibration
- [ ] Tune T_high, T_low, ema_beta on benign dataset
- [ ] Target: <0.1% FPR while maintaining >95% recall

---

## Maintenance Tasks

### Structured Outputs Investigation
- [ ] Research Ollama structured outputs / JSON mode for classification
- [ ] Test constrained generation to force SAFE/FAIL output
- [ ] Compare accuracy: logprobs vs structured outputs vs text generation

### Polish
- [x] Fix stream break timing bug (classifications now queued, not blocking)
- [x] Fix ASCII chart reset between messages
- [ ] Add `has_logit_extraction` flag to ApprovedModel enum
- [ ] Unify prompt building to template-only (remove legacy few-shot scaffolding)

### Performance
- [x] Non-blocking classification with queue-based processing
  - Classifications are queued by `on_user_type` (fast, non-blocking)
  - Timer processes ONE classification per tick (every 500ms)
  - Stream break waits for `pending_classifications` queue to empty
  - Fixes race condition where stream break could fire before all words classified
  - See `docs/stream.md` for architecture analysis

### Documentation
- [ ] Add troubleshooting guide
- [ ] Write technical blog post comparing to CC++ jailbreak detection
