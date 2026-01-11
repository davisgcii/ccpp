# TODO.md

# CC++-Inspired Streaming Exchange Classifier → Streaming PII Masker

This TODO implements a CC++-style **exchange classifier cascade** for **streaming detection + masking** of PII/sensitive info when guarding a **black-box hosted LLM**.

## Phase 1: Foundations

### Constitutions
- [x] Create `constitutions/pii_sensitive.md`
  - [x] Define reason codes (safe, pii/direct, pii/indirect, credentials, financial, medical, location/precise)
  - [x] Boundary cases (public vs private contact info; placeholders; redaction examples)
  - [x] Explicit "allowed" examples to reduce false positives (fake tokens, templates, docs)
- [x] Create `constitutions/harmless.md`
  - [x] Examples of benign content that resembles PII but is not (e.g., `<EMAIL>`, `example.com`, fake numbers)
  - [x] Guidance on when to *not* mask (e.g., docs about "what is an email address")

## Phase 2: Runtime Guard (streaming masking)

### Core streaming state machine (required)
- [x] Implement `src/ccpp/types.py`:
  - [x] `HoldbackBuffer` (raw text buffer + overlap tail)
  - [x] `RiskState` (EMA smoothing, hysteresis thresholds, routing state)
  - [x] `MaskSpan` (entity text + category, NOT offsets)
  - [x] `RedactorOutput` (with `apply_masks()` using exact string matching)
- [x] Implement `src/ccpp/infer/guard.py`:
  - [x] `ExchangePIIGuard` with:
    - [x] `ingest_chunk(text)` - per-token/chunk ingestion
    - [x] `force_emit()` - force emission at end of stream
    - [x] Returns `emit_text` (already redacted) and `events` (risk updates, masking)
  - [x] Stream break detection (timeout-based, default 500ms)
  - [x] Three-condition masking: any_risk_in_buffer OR ema≥T_high OR strong_match
  - [x] No EMA reset by default (natural decay across stream breaks)
  - [x] Default behavior: **no unmasking** (irreversible once emitted)

### Stage 1 router (runs per-token, not chunked)
- [x] Implement `src/ccpp/infer/stage1_router.py`:
  - [x] Mock mode: heuristic-based P(RISK) scoring
  - [ ] Real mode: Load stage1 model
  - [ ] Real mode: **Logit-based classification** (single forward pass)
    - [ ] Extract P(RISK) from softmax over SAFE/RISK token logits
    - [ ] No text generation (5-6x faster than autoregressive)
  - [ ] Exchange-aware: full conversation context + current buffer

### Fast heuristics (always-on)
- [x] Implement `src/ccpp/infer/heuristics.py`:
  - [x] Regex detectors: email, phone, SSN, credit card (with Luhn), AWS keys, Stripe keys, GitHub tokens, PEM blocks
  - [x] Validators: Luhn check, allowlists for `example.com`, test cards, test phone numbers, test SSNs
  - [x] Returns `list[HeuristicMatch]` with confidence scores
  - [x] If confidence ≥ 0.9 → strong_match → route to stage2

### Stage 2 span redactor (routed traffic at stream breaks)
- [x] Implement `src/ccpp/infer/stage2_redactor.py`:
  - [x] Mock mode: regex-based entity extraction
  - [ ] Real mode: Load stage2 model (Qwen3-7B)
  - [ ] Real mode: Input: context + buffer with overlap tail
  - [ ] Real mode: Output: `PASS` or `MASK "entity_text" category; ...`
    - [ ] **Entity text format** (NOT character offsets - LLMs bad at counting)
    - [ ] Quoted strings to handle spaces/special chars
  - [x] Apply masks using exact string matching
  - [x] Mask format: `[{type}]` (e.g., `[PII/DIRECT]`)

### Demo (simulated streaming)
- [x] `scripts/demo.py`:
  - [x] Character-by-character streaming simulation
  - [x] Visual risk meter with color-coded output
  - [x] 6 scenarios: email, phone, benign, multiple entities, partial detection, API key
  - [x] Interactive mode (`-i` flag)
  - [ ] TODO: Integrate with actual base model API streaming

### Interactive GUI client (real-time user testing)
- [ ] `scripts/gui_client.py` - **Pop-up window application** (NOT CLI):
  - [ ] **Input display (top)**:
    - [ ] Show user's text as they type in real-time
    - [ ] Risk indicators appear under words that trigger risk
  - [ ] **Real-time risk chart (bottom)**:
    - [ ] Live chart showing P(RISK) and EMA over time
    - [ ] Horizontal threshold line (T_high) clearly visible
    - [ ] EMA line turns red when crossing threshold
    - [ ] Updates continuously as user types
  - [ ] **Stream break and masking**:
    - [ ] Pause detection based on configured timeout (default 3s)
    - [ ] After pause, run masker on buffered text
    - [ ] Display masked version directly below original text (side-by-side comparison)
  - [ ] **Base model streaming**:
    - [ ] Send masked text to base model (Anthropic Claude)
    - [ ] Stream response back in window
    - [ ] **Interruption handling**: If user starts typing during response:
      - [ ] Pause the response streaming
      - [ ] Only include displayed portion in conversation history
      - [ ] Discard unplayed portion of response
  - [ ] **UI Framework**: TBD (options: tkinter, PyQt, Gradio, Streamlit)
- [x] Environment setup:
  - [x] `.env` file for API keys (ANTHROPIC_API_KEY)
  - [x] `.env.example` template
  - [x] `.gitignore` to exclude `.env`, models, datasets
- [ ] `scripts/client.py` (CLI version - basic, for debugging only):
  - [x] Basic parameter fix for ExchangePIIGuard
  - [ ] Note: This is NOT the main interactive client (see gui_client.py above)

## Phase 3: Synthetic data generation (with entity labels)

### Dataset schema

**Stage 1 (Router) Training Data:**
Each record should include:
- `messages`: list[{"role": ..., "content": ...}] (exchange context - may include historical PII)
- `current_buffer`: the text being classified (current utterance/buffer only)
- `label`: `SAFE` or `RISK` (binary)
- **CRITICAL**: Label applies to `current_buffer` only, NOT entire exchange
  - Historical PII in `messages` does NOT cause RISK label
  - Only flag RISK if PII is in current_buffer
- `meta`: generation provenance

**Stage 2 (Redactor) Training Data:**
Each record should include:
- `messages`: list[{"role": ..., "content": ...}] (exchange context)
- `window_text`: the exact redaction window presented to stage2 (buffer + overlap tail)
- `entities`: list[{entity_text: str, category: str}] - the actual entity strings to mask
- `target_output`: `PASS` or `MASK "entity1" category1; MASK "entity2" category2`
- `meta`: generation provenance

### Generator
- [ ] Implement `src/generate_data/generator.py`:
  - [ ] Create prompts that lead to PII-like emissions using **placeholders**:
    - `<EMAIL>`, `<PHONE>`, `<NAME>`, `<ADDRESS>`, `<TOKEN>`, `<ACCOUNT_NUMBER>`
  - [ ] Generate text containing placeholders
  - [ ] Hydrate placeholders with synthetic PII (for training safety)
  - [ ] For Stage 1: Create buffer-scoped labels
    - If placeholder in current buffer → RISK
    - If placeholder only in historical context → SAFE
  - [ ] For Stage 2: Extract entity text (not offsets)
    - Format: `MASK "actual_entity_text" category`
  - [ ] Also generate benign "near misses" (example.com, 555-0100 style, test keys)
  - [ ] Filter refusals if using any safety-aware generator

### CLI
- [ ] `scripts/generate_data.py` (`ccpp-generate`)
  - [ ] Output JSONL train/val splits
  - [ ] Separate files for stage1 and stage2 training data

## Phase 4: Augmentations (reconstruction/obfuscation analogs)

### Basic augmentations
- [ ] Paraphrase, translate/back-translate, formatting (tables/code blocks), role-play wrappers

### Reconstruction-style augmentations (PII version)
- [ ] Split entities across turns/stream breaks:
  - [ ] "it's george" + [break] + "george.davis@gmail.com"
  - [ ] "email notification at" + [break] + "george@gmail.com"
  - [ ] `sk_live_` + remainder in later utterance
- [ ] Insert separators/spaces/unicode homoglyphs within entities
- [ ] "Contact card" formatting and re-assembly

### Entity text remains valid after augmentation
- [ ] Since we use entity text (not offsets), augmentations are easier
- [ ] Just ensure entity strings are still extractable from augmented text
- [ ] No need to update character offsets

### CLI
- [ ] `scripts/augment.py` (`ccpp-augment`)

## Phase 5: Training

### Libraries/stack
- PyTorch + Hugging Face:
  - `transformers`, `datasets`, `accelerate`, `peft`, `trl`, `bitsandbytes`
- Use `uv` to manage dependencies.

### Stage 1 training (logit-based router)
- [ ] Implement `src/train/train_stage1.py`:
  - [ ] **Logit-based classification** (NOT text generation)
    - [ ] Train model to predict "SAFE" or "RISK" as next token
    - [ ] At inference: extract P(RISK) from softmax over SAFE/RISK token logits
    - [ ] No autoregressive generation needed (5-6x faster)
  - [ ] **Softmax-weighted loss** (from CC++ paper):
    - [ ] For each training example, run forward pass on all token positions in buffer
    - [ ] Apply sliding window smoothing (M=16) to logits
    - [ ] Weight positions by softmax(z_bar / temperature)
    - [ ] Addresses temporal "when to flag" problem within buffer
  - [ ] **Buffer-scoped labels** (critical!):
    - [ ] Label = RISK only if PII in current_buffer
    - [ ] Historical PII in context → label = SAFE
    - [ ] Context provides semantic understanding, not classification target
  - [ ] LoRA fine-tuning on Qwen3-1.7B
  - [ ] Target format: next token should be "SAFE" or "RISK"

### Stage 2 training (entity redactor)
- [ ] Implement `src/train/train_stage2.py`:
  - [ ] Supervised fine-tuning to output `PASS` or `MASK "entity" category; ...`
  - [ ] **Entity text format** (NOT character offsets)
  - [ ] Use placeholders in training data for safety
  - [ ] Ensure window_text is provided exactly as in inference (buffer + overlap tail)
  - [ ] Constrain max_new_tokens and use greedy decoding for determinism
  - [ ] LoRA fine-tuning on Qwen3-7B.

### Configs
- [ ] `configs/stage1.yaml` (includes softmax temperature, window size M, etc.)
- [ ] `configs/stage2.yaml`

### CLI
- [ ] `scripts/train.py` (`ccpp-train`)

## Phase 6: Evaluation + calibration

### Metrics
- [ ] Entity-level precision/recall/F1 for stage2
  - [ ] Exact string match: extracted entity exactly matches ground truth
  - [ ] Partial match: extracted entity overlaps with ground truth
- [ ] Entity-type confusion matrix
- [ ] False positive rate on benign corpora (e.g., WildChat)
  - [ ] Target: <0.1% mask rate on benign text
- [ ] Stage 1 calibration:
  - [ ] Stage 2 escalation rate (~10-20% expected)
  - [ ] Recall on known PII test set (>95%)
- [ ] Streaming behavior:
  - [ ] Characters leaked before masking (should be ~0 with stream break detection)
  - [ ] Latency overhead per token (Stage 1: <20ms, Stage 2: <100ms)
  - [ ] End-to-end latency per utterance

### Calibration
- [ ] Pick benign dataset (e.g., WildChat subset) and tune:
  - [ ] `T_high` (escalation threshold, default 0.6)
  - [ ] `T_low` (de-escalation threshold, default 0.3)
  - [ ] `ema_beta` (smoothing factor, default 0.85)
  - [ ] `stream_break_timeout` (default 500ms)
  - [ ] `risk_threshold_immediate` (any_risk_in_buffer threshold, default 0.7)
- [ ] Target: <0.1% FPR on benign while maintaining >95% recall on PII test set
- [ ] Test cross-break detection with split entities

### CLI
- [ ] `scripts/eval.py` (`ccpp-eval`)

## Phase 7: Documentation
- [x] `CLAUDE.md` with:
  - [x] Per-token architecture diagram (stream break detection, three-condition masking)
  - [x] Detailed conversation example (18 turns with cross-break detection)
  - [x] EMA decay behavior explanation
  - [x] Buffer-scoped label training approach
  - [x] Fast heuristics patterns and allowlists
- [ ] `README.md` with:
  - [ ] Project overview and motivation
  - [ ] Quick start guide
  - [ ] Architecture diagram
  - [ ] How this maps to CC++ exchange classifiers + cascades
  - [ ] Demo usage examples
- [ ] Blog post / technical writeup:
  - [ ] Comparison to CC++ jailbreak detection
  - [ ] Why PII masking needs different label scope (buffer-scoped vs exchange-scoped)
  - [ ] Cross-break detection enabled by EMA persistence
  - [ ] Entity text vs character offsets tradeoff

---

## Current Status (update as you go)
**Last Updated**: 2026-01-10 (evening)

### Confirmed Architectural Decisions

**Core Architecture:**
- **Approach**: Streaming Masking (detect PII entities, redact them, continue streaming)
- **Per-token Classification**: Stage 1 runs on every new token/chunk (NOT K=32 chunking)
- **Stream Break Detection**: Timeout-based (default 500ms), mimics VAD breaks in speech-to-text
- **No Blocking**: System masks and continues rather than refusing/stopping

**Stage 1 (Router):**
- **Output**: Logit-based P(RISK) ∈ [0,1] from softmax over SAFE/RISK tokens
- **Speed**: 5-6x faster than text generation (single forward pass, no autoregressive)
- **Training**: Softmax-weighted loss to handle temporal "when to flag" problem
- **Label Scope**: Buffer-scoped (current buffer only, NOT entire exchange)
  - Historical PII in context → label = SAFE
  - Only flag RISK if PII in current_buffer

**Stage 2 (Redactor):**
- **Output**: Entity text format `MASK "entity_text" category` (NOT character offsets)
- **Rationale**: LLMs are bad at counting characters but good at recognizing entities
- **Masking**: Exact string matching with quote escaping

**Risk Management:**
- **EMA Smoothing**: beta=0.85, naturally decays (no reset by default)
- **Hysteresis**: T_high=0.6 (escalate), T_low=0.3 (de-escalate)
- **Three-condition masking**: any_risk_in_buffer OR ema≥T_high OR strong_heuristic_match
- **any_risk_in_buffer**: Set if any token has P(RISK) ≥ 0.7 (resets at stream breaks)

**Label Schema:**
- 7 categories: safe, pii/direct, pii/indirect, credentials, financial, medical, location/precise

### Completed Tasks (Phase 2 - Mock Implementation)
- [x] Rewrite `src/ccpp/types.py` with PII-focused types
  - [x] `PIICategory`, `RiskScore` (with `from_logits()`), `MaskSpan` (entity text)
  - [x] `RedactorOutput` (with `apply_masks()` using exact string matching)
  - [x] `HoldbackBuffer` (with overlap tail), `RiskState` (EMA + hysteresis)
- [x] Create `constitutions/pii_sensitive.md` with entity text examples
- [x] Create `constitutions/harmless.md` (benign patterns, allowlists)
- [x] Implement `src/ccpp/infer/heuristics.py` (regex detectors with allowlists)
- [x] Implement `src/ccpp/infer/stage1_router.py` (mock: heuristic-based P(RISK))
- [x] Implement `src/ccpp/infer/stage2_redactor.py` (mock: regex-based entity extraction)
- [x] Implement `src/ccpp/infer/guard.py` (ExchangePIIGuard with full streaming logic)
- [x] Implement `scripts/demo.py` (6 scenarios + interactive mode)
- [x] Implement `scripts/client.py` (basic CLI debugging client - fixed parameter names)
- [x] Update `CLAUDE.md` with:
  - [x] Per-token architecture diagram
  - [x] Detailed conversation example with 18 turns
  - [x] EMA decay behavior (no reset)
  - [x] Buffer-scoped label explanation

### Next Steps
1. **Phase 2 (continued)**: Implement GUI interactive client (`scripts/gui_client.py`)
   - Choose UI framework (tkinter, PyQt, Gradio, or Streamlit)
   - Build pop-up window with real-time chart (P(RISK) and EMA with threshold lines)
   - Visual risk indicators under words as they trigger
   - Side-by-side original/masked text comparison
   - Response streaming with interruption handling (pause on user typing)
   - Only include displayed portion of interrupted responses in history
2. **Phase 3**: Implement synthetic data generation
   - Create Stage 1 training data with buffer-scoped labels
   - Create Stage 2 training data with entity text format
3. **Phase 4**: Implement augmentations (cross-break entity splitting)
4. **Phase 5**: Implement real model training
   - Stage 1: Logit-based with softmax-weighted loss
   - Stage 2: Entity text generation
5. **Phase 6**: Evaluation + calibration on real data
