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

### Not Started
- Structured outputs for reliable SAFE/FAIL classification
- Training data generation
- Model fine-tuning
- Evaluation and calibration

---

## Phase 3: Synthetic Data Generation

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
- [ ] Create prompts using placeholders (`<EMAIL>`, `<PHONE>`, `<NAME>`, etc.)
- [ ] Hydrate placeholders with synthetic PII
- [ ] Generate buffer-scoped labels for Stage 1
- [ ] Generate benign "near misses" (example.com, test keys)
- [ ] Output JSONL train/val splits

---

## Phase 4: Data Augmentation

### Basic Augmentations
- [ ] Paraphrase, translate/back-translate
- [ ] Formatting variations (tables, code blocks)
- [ ] Role-play wrappers

### Reconstruction-Style Augmentations
- [ ] Split entities across stream breaks: "it's george" + [break] + "@gmail.com"
- [ ] Insert separators/unicode within entities
- [ ] "Contact card" formatting

---

## Phase 5: Training

### Stage 1 (Logit-Based Router)
- [ ] Train for next-token prediction (SAFE/FAIL)
- [ ] Implement softmax-weighted loss (CC++ paper)
- [ ] Buffer-scoped labels (critical!)
- [ ] LoRA fine-tuning on Qwen3-1.7B

### Stage 2 (Entity Redactor)
- [ ] Supervised fine-tuning for `MASK "entity" category` output
- [ ] Use placeholders in training data
- [ ] LoRA fine-tuning on Qwen3-7B

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
- [ ] Manual GUI testing (end-to-end flow)
- [ ] Add `has_logit_extraction` flag to ApprovedModel enum
- [ ] Unify prompt building to template-only (remove legacy few-shot scaffolding)

### Documentation
- [ ] Add troubleshooting guide
- [ ] Write technical blog post comparing to CC++ jailbreak detection
