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
- 132 unit/integration tests passing
- Prompt templates with `Answer:` ending (prevents model echo)
- Qwen3 `think=False` integration
- Training data generation pipeline (`data/scripts/`)
  - Synthetic conversation generator using Claude Haiku
  - Stage 1 formatter (speculative prefix classification)
  - Stage 2 formatter (entity extraction training)
  - Constitution loader for PII definitions
- LoRA finetuning pipeline with mlx-lm
  - Stage 1 adapter: `models/adapters/stage1/qwen3-0.6b-pii-classifier/`
  - Stage 2 adapter: `models/adapters/stage2/qwen3-1.7b-pii-redactor/`
- Wandb integration for training loss visualization

### In Progress
- Evaluation and calibration refinement
- Structured outputs for reliable SAFE/FAIL classification

---

## Completed Phases

### Phase 3: Synthetic Data Generation ✅
Pipeline implemented in `data/scripts/`. See `data/README.md` for format details.
- [x] Synthetic conversation generator (Claude Haiku)
- [x] Stage 1 prefix classification formatter
- [x] Stage 2 entity extraction formatter
- [ ] Generate benign "near misses" (example.com, test keys) — needs more examples
- [ ] Output JSONL train/val splits with proper ratio

### Phase 4: Data Augmentation (Partial)
- [x] Split entities across stream breaks (5% of PII conversations)
- [ ] Paraphrase, translate/back-translate
- [ ] Formatting variations (tables, code blocks)
- [ ] Insert separators/unicode within entities

### Phase 5: Training ✅
LoRA fine-tuning via mlx-lm on Apple Silicon:
- Stage 1 adapter: `models/adapters/stage1/qwen3-0.6b-pii-classifier/` (val_loss 5.38 → 0.028)
- Stage 2 adapter: `models/adapters/stage2/qwen3-1.7b-pii-redactor/` (val_loss 0.28 → 0.070)
- [ ] Validate SAFE/FAIL accuracy on held-out test set
- [ ] Validate entity extraction accuracy

See `CLAUDE.md` for full training commands and Qwen3 thinking-token details.

---

## Phase 6: Evaluation

### Metrics
- [ ] Entity-level precision/recall/F1 (exact and partial match)
- [ ] False positive rate on benign corpora (<0.1% target)
- [ ] Stage 2 escalation rate (~10-20%)

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
