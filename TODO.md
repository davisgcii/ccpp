# TODO.md

# CC++-Inspired Streaming Exchange Classifier → Streaming PII Masker

This TODO implements a CC++-style **exchange classifier cascade** for **streaming detection + masking** of PII/sensitive info when guarding a **black-box hosted LLM**.

## CRITICAL ISSUES (Current GUI Bugs)

### Issue #1: GUI Processing Hangs After Metadata Building
**STATUS**: 🔴 BLOCKING - UI never updates despite successful backend processing

**Symptoms**:
- User types text, pauses 3s
- Stream break triggers correctly
- Stage 2 extracts entities successfully
- Logs stop at "FLOW: Building metadata" (app.py:303)
- Never reaches "FLOW: Added user message" (app.py:336)
- UI never shows masked text or LLM response

**Investigation**:
```python
# app.py:314-335 - Silent failure zone
buffer_metadata = BufferMetadata(
    original_text=original_text,
    masked_text=masked_text,
    char_data=state.current_char_data.copy(),  # Possible issue?
    ...
)
state.add_to_conversation({
    "role": "user",
    "content": masked_text,
    "metadata": buffer_metadata.to_dict(),  # Crashes here?
})
```

**Evidence from logs** (2026-01-10 20:09:23):
```
[INFO] [check_and_process_buffer] Masked 'george@gmail.com' -> '[PII/DIRECT]'
[INFO] [check_and_process_buffer] FLOW: Post-masking - original_len=88, masked_len=84, was_masked=True
[DEBUG] [check_and_process_buffer] FLOW: Marked buffer as processed
[DEBUG] [check_and_process_buffer] FLOW: Building metadata - was_masked=True, char_data_len=15, risk_history_len=15
# LOGS STOP HERE - never reaches line 336
```

**Possible causes**:
1. `BufferMetadata()` constructor failing silently
2. `buffer_metadata.to_dict()` raising unhandled exception
3. `state.current_char_data` contains incompatible data (only 15 entries for 88 chars)
4. Gradio thread being killed without logging
5. Silent exception in try/except block swallowing error

**Next steps**:
- [ ] Add try/except with explicit logging around BufferMetadata creation
- [ ] Add try/except with explicit logging around to_dict() call
- [ ] Validate char_data structure before creating BufferMetadata
- [ ] Test BufferMetadata.to_dict() in isolation with actual data
- [ ] Check if Gradio has output size limits causing silent failures

---

### Issue #2: Gradio Event Batching Causes Missing Datapoints
**STATUS**: 🟡 DESIGN ISSUE - Not a bug, but architectural mismatch

**Symptoms**:
- User types 88 characters
- Only 15 RISK datapoints appear in chart
- Gaps in visualization between characters

**Root cause**:
- Gradio's `.input()` event fires in **batches**, not per-character
- User types quickly → Gradio combines keystrokes into single events
- `on_user_type()` called with full text so far, but only adds ONE risk_history entry per call

**Evidence from logs**:
```
20:09:06 - Received text: length=1   (char 'c')
20:09:15 - Received text: length=67  (Gradio batched 66 chars!)
20:09:15 - Received text: length=73  (batched 6 more)
20:09:16 - Received text: length=79  (batched 6 more)
20:09:16 - Received text: length=81  (batched 2 more)
20:09:17 - Received text: length=88  (batched 7 more)
# Total: 5 events for 88 characters
```

**Why this happens**:
- Gradio optimizes by batching rapid input events
- Each batch contains **entire text so far**, not just new characters
- GUI processes Stage 1 on full buffer but only adds one datapoint

**Architectural mismatch**:
- Backend designed for **per-token streaming** from LLM output
- GUI trying to use it for **user typing** (batched input events)

**Solutions**:
1. **Track previous length** - only process new characters:
   ```python
   prev_len = len(state.prev_buffer or "")
   curr_len = len(user_input)
   new_chars = user_input[prev_len:curr_len]
   # Process each new character individually
   ```
2. **Redesign for batch mode** - accept that GUI won't be truly per-character
3. **Use WebSocket** - bypass Gradio's batching with raw streaming

---

### Issue #3: RISK Scores "Max Out" at 1.000
**STATUS**: ✅ NOT A BUG - Working correctly!

**What looks wrong**:
- Chart legend shows "RISK=1.000"
- All datapoints after character 66 show P(RISK)=1.000

**Why this is correct**:
```
char 66: '@'      → P(RISK)=0.989 (high confidence - email pattern)
char 72: 'g'      → P(RISK)=1.000 (definitely part of email)
char 78: 'm'      → P(RISK)=1.000 (still in email)
char 80: 'a'      → P(RISK)=1.000 (still in email)
char 87: 'com'    → P(RISK)=1.000 (completing email domain)
```

**Evidence**: Stage 2 correctly extracted `george@gmail.com` as PII/DIRECT

**Conclusion**: Model is correctly flagging email characters as maximum risk. This is expected behavior.

---

## What IS Working ✅

### Backend Processing (All Functional)
- [x] **MLX backend** - True logit extraction with calibrated probabilities
  - Stage 1: 6 few-shot examples, 1224-char system prompt
  - Stage 2: 6 few-shot examples, 1600-char system prompt
  - Qwen/Qwen3-1.7B-MLX-8bit loaded and functional
- [x] **Stream break detection** - Triggers correctly after 3s timeout
- [x] **Heuristics** - Email pattern detected with confidence=1.0
- [x] **any_risk_in_buffer flag** - Correctly set when P(RISK) ≥ 0.7
- [x] **Stage 2 entity extraction** - Successfully extracts entities:
  ```
  Input: "...my email address -- george@gmail.com"
  Output: MASK "george@gmail.com" pii/direct
  Masked: "...my email address -- [PII/DIRECT]"
  ```
- [x] **EMA smoothing** - Correctly tracks risk over time:
  ```
  char 66: p_risk=0.989, ema=0.276
  char 72: p_risk=1.000, ema=0.384
  char 78: p_risk=1.000, ema=0.477
  char 80: p_risk=1.000, ema=0.555
  char 87: p_risk=1.000, ema=0.622 (exceeds T_high=0.6)
  ```

---

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
  - [x] `BufferMetadata` - Per-buffer metadata with char_data and risk_history
  - [x] `CharClassification` - Per-character debugging metadata
- [x] Implement `src/ccpp/infer/guard.py`:
  - [x] `ExchangePIIGuard` with:
    - [x] `ingest_chunk(text)` - per-token/chunk ingestion
    - [x] `force_emit()` - force emission at end of stream
    - [x] Returns `emit_text` (already redacted) and `events` (risk updates, masking)
  - [x] Stream break detection (timeout-based, default 500ms, configurable to 3s)
  - [x] Three-condition masking: any_risk_in_buffer OR ema≥T_high OR strong_match
  - [x] No EMA reset by default (natural decay across stream breaks)
  - [x] Default behavior: **no unmasking** (irreversible once emitted)

### Stage 1 router (runs per-token, not chunked)
- [x] Implement `src/ccpp/infer/stage1_router.py`:
  - [x] Mock mode: heuristic-based P(RISK) scoring
  - [x] Real mode: MLX backend with true logit extraction
    - [x] Extract P(RISK) from softmax over SAFE/RISK token logits
    - [x] Single forward pass (5-6x faster than text generation)
    - [x] Calibrated probabilities (not fake binary 0.0/1.0)
  - [x] Exchange-aware: full conversation context + current buffer
  - [x] Few-shot examples (6 examples with context)
  - [x] Comprehensive system prompt (1224 chars)

### Fast heuristics (always-on)
- [x] Implement `src/ccpp/infer/heuristics.py`:
  - [x] Regex detectors: email, phone, SSN, credit card (with Luhn), AWS keys, Stripe keys, GitHub tokens, PEM blocks
  - [x] Validators: Luhn check, allowlists for `example.com`, test cards, test phone numbers, test SSNs
  - [x] Returns `list[HeuristicMatch]` with confidence scores
  - [x] If confidence ≥ 0.9 → strong_match → route to stage2

### Stage 2 span redactor (routed traffic at stream breaks)
- [x] Implement `src/ccpp/infer/stage2_redactor.py`:
  - [x] Mock mode: regex-based entity extraction
  - [x] Real mode: MLX backend with text generation
    - [x] Input: context + buffer with overlap tail
    - [x] Output: `PASS` or `MASK "entity_text" category; ...`
    - [x] Entity text format (NOT character offsets)
    - [x] Quoted strings to handle spaces/special chars
  - [x] Apply masks using exact string matching
  - [x] Mask format: `[{type}]` (e.g., `[PII/DIRECT]`)
  - [x] Few-shot examples (6 examples with multi-entity cases)
  - [x] Comprehensive system prompt (1600 chars)

### LLM Backend Harness
- [x] Implement `src/ccpp/llm/base.py` - Base classes for backends
- [x] Implement `src/ccpp/llm/factory.py` - Backend factory with routing
- [x] Implement `src/ccpp/llm/ollama_backend.py` - Ollama integration (text-based, fake probabilities)
- [x] Implement `src/ccpp/llm/mlx_backend.py` - **MLX integration** (TRUE logit extraction)
  - [x] Load Qwen3-1.7B-MLX-8bit from HuggingFace
  - [x] extract_logit_probs() - Extract raw logits and apply softmax
  - [x] generate() - Text generation with temperature control
  - [x] Token ID caching for SAFE/RISK tokens
- [x] Implement `src/ccpp/llm/anthropic_backend.py` - Anthropic API
- [x] Implement `src/ccpp/llm/openai_backend.py` - OpenAI API

### Configuration System
- [x] Implement `src/ccpp/config.py`:
  - [x] YAML-based config loading with inheritance
  - [x] Environment-specific configs (default, dev, prod)
  - [x] Runtime overrides via environment variables
  - [x] Config extraction functions for Stage 1 and Stage 2
  - [x] Model name validation (ApprovedModel enum)
- [x] Create `configs/default.yaml`:
  - [x] MLX backend configuration
  - [x] Stage 1: 6 few-shot examples, comprehensive prompting
  - [x] Stage 2: 6 few-shot examples, comprehensive prompting
  - [x] Stream break timeout: 2000ms (2s for voice)
  - [x] EMA beta: 0.85, thresholds (T_high=0.6, T_low=0.3, risk=0.7)

### Demo (simulated streaming)
- [x] `scripts/demo.py`:
  - [x] Character-by-character streaming simulation
  - [x] Visual risk meter with color-coded output
  - [x] 6 scenarios: email, phone, benign, multiple entities, partial detection, API key
  - [x] Interactive mode (`-i` flag)

### Interactive GUI client (real-time user testing)
- [x] `scripts/gui_client.py` - **Pop-up window application** (Gradio-based):
  - [x] **Module structure** (`src/ccpp/gui/`):
    - [x] `state.py` - State management with thread safety
    - [x] `components.py` - Chart and HTML generation
    - [x] `app.py` - Main Gradio interface and event handlers
  - [x] **Input display (top)**:
    - [x] Show user's text as they type in real-time (Textbox.input)
    - [x] Risk indicators appear under words that trigger risk (HTML with red highlights)
  - [x] **Real-time risk chart (bottom)**:
    - [x] ASCII art chart with P(RISK) and EMA (box-drawing characters)
    - [x] Horizontal threshold lines (T_high and T_low) clearly visible
    - [x] EMA blocks turn red when crossing threshold
    - [x] Updates continuously as user types
  - [x] **Stream break and masking**:
    - [x] Pause detection based on configured timeout (3s via Timer)
    - [x] After pause, run masker on buffered text
    - [x] Display masked version (would work if not for metadata bug)
  - [x] **Base model streaming**:
    - [x] Anthropic Claude integration ready
    - [x] Interruption handling implemented
  - [x] **UI Framework**: Gradio (web-based terminal aesthetic)
- [x] Environment setup:
  - [x] `.env` file for API keys (ANTHROPIC_API_KEY)
  - [x] `.env.example` template
  - [x] `.gitignore` to exclude `.env`, models, datasets
- [x] `scripts/client.py` (CLI version - basic, for debugging only)

### Debugging and Logging
- [x] Comprehensive logging at all stages:
  - [x] Stage 1: few-shot count, prompt length, logit values
  - [x] Stage 2: few-shot count, prompt length, entity extraction
  - [x] FLOW logs: trace execution through processing pipeline
  - [x] DEBUG logs: character-level detail, timer events

---

## IMMEDIATE PRIORITIES (Before continuing to Phase 3)

### 1. Fix GUI Metadata Crash 🔴 CRITICAL
- [ ] Add explicit try/except around BufferMetadata creation (app.py:314)
- [ ] Add explicit try/except around to_dict() call (app.py:333)
- [ ] Log exact exception and traceback
- [ ] Test BufferMetadata serialization in isolation
- [ ] Fix or work around the crash
- [ ] Verify UI updates after fix

### 2. Fix or Accept Gradio Event Batching 🟡 IMPORTANT
- [ ] **Option A**: Track previous buffer length, process only new characters
- [ ] **Option B**: Document as known limitation of Gradio-based GUI
- [ ] **Option C**: Redesign GUI for batch-mode processing (update chart less frequently)
- [ ] **Option D**: Replace Gradio with WebSocket-based streaming (major refactor)

### 3. Model Enum Restructure 🟡 CLEANUP
- [ ] Restructure ApprovedModel by provider:
  ```python
  class ApprovedModel(Enum):
      # MLX models (local, true logit extraction)
      MLX_QWEN3_1_7B_8BIT = "Qwen/Qwen3-1.7B-MLX-8bit"

      # Ollama models (local, fake probabilities)
      OLLAMA_QWEN3_1_7B = "qwen3:1.7b"

      # Anthropic models (API)
      CLAUDE_HAIKU_4_5 = "claude-haiku-4-5-20251001"

      # OpenAI models (API)
      GPT_5_MINI = "gpt-5-mini"
  ```
- [ ] Add metadata: `has_logit_extraction: bool` flag
- [ ] Enforce: Stage 1 MUST use model with logit extraction
- [ ] Update all configs and tests

### 4. Integration Tests 🟡 VALIDATION
- [ ] Add MLX backend integration tests
- [ ] Test logit extraction with real model
- [ ] Test Stage 2 entity extraction with real model
- [ ] Test end-to-end pipeline with MLX backend

### 5. Documentation Updates 🟢 POLISH
- [ ] Update README with current MLX backend status
- [ ] Add "Known Issues" section to README
- [ ] Update CLAUDE.md with MLX backend details
- [ ] Document Gradio event batching limitation
- [ ] Add troubleshooting guide

### 6. Cleanup 🟢 HOUSEKEEPING
- [ ] Delete unnecessary files:
  - [ ] GUI_IMPLEMENTATION_PLAN.md (archived to docs/)
  - [ ] GUI_REQUIREMENTS.md (archived to docs/)
  - [ ] src/ccpp/gui/components.py.backup
  - [ ] Any old config files (stage1_llm.yaml, stage2_llm.yaml if unused)
- [ ] Update .gitignore for MLX model cache
- [ ] Review and clean up logs

---

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
  - [x] Project overview and motivation
  - [x] Quick start guide
  - [x] Architecture diagram
  - [x] Configuration system documentation
  - [x] Demo usage examples
  - [ ] **UPDATE NEEDED**: MLX backend status, known GUI issues
- [ ] Blog post / technical writeup:
  - [ ] Comparison to CC++ jailbreak detection
  - [ ] Why PII masking needs different label scope (buffer-scoped vs exchange-scoped)
  - [ ] Cross-break detection enabled by EMA persistence
  - [ ] Entity text vs character offsets tradeoff
  - [ ] MLX vs Ollama logit extraction comparison

---

## Current Status (update as you go)
**Last Updated**: 2026-01-10 23:00

### Confirmed Architectural Decisions

**Core Architecture:**
- **Approach**: Streaming Masking (detect PII entities, redact them, continue streaming)
- **Per-token Classification**: Stage 1 runs on every new token/chunk (NOT K=32 chunking)
- **Stream Break Detection**: Timeout-based (default 500ms, GUI uses 3s), mimics VAD breaks in speech-to-text
- **No Blocking**: System masks and continues rather than refusing/stopping

**Stage 1 (Router):**
- **Backend**: MLX with Qwen/Qwen3-1.7B-MLX-8bit
- **Output**: Logit-based P(RISK) ∈ [0,1] from softmax over SAFE/RISK tokens
- **Speed**: 5-6x faster than text generation (single forward pass, no autoregressive)
- **Prompting**: 6 few-shot examples + 1224-char system prompt
- **Label Scope**: Buffer-scoped (current buffer only, NOT entire exchange)
  - Historical PII in context → label = SAFE
  - Only flag RISK if PII in current_buffer

**Stage 2 (Redactor):**
- **Backend**: MLX with Qwen/Qwen3-1.7B-MLX-8bit (same model as Stage 1 for now)
- **Output**: Entity text format `MASK "entity_text" category` (NOT character offsets)
- **Rationale**: LLMs are bad at counting characters but good at recognizing entities
- **Prompting**: 6 few-shot examples + 1600-char system prompt
- **Masking**: Exact string matching with quote escaping
- **Working**: Successfully extracts entities like `george@gmail.com` → `[PII/DIRECT]`

**Risk Management:**
- **EMA Smoothing**: beta=0.85, naturally decays (no reset by default)
- **Hysteresis**: T_high=0.6 (escalate), T_low=0.3 (de-escalate)
- **Three-condition masking**: any_risk_in_buffer OR ema≥T_high OR strong_heuristic_match
- **any_risk_in_buffer**: Set if any token has P(RISK) ≥ 0.7 (resets at stream breaks)
- **Working**: Correctly tracks risk and triggers masking decisions

**Label Schema:**
- 7 categories: safe, pii/direct, pii/indirect, credentials, financial, medical, location/precise

### Completed Tasks ✅

**Phase 2 - Core Implementation:**
- [x] All core types and state machines
- [x] ExchangePIIGuard with streaming logic
- [x] Fast heuristics with allowlists
- [x] Stage 1 router with MLX backend and true logit extraction
- [x] Stage 2 redactor with MLX backend and entity extraction
- [x] LLM harness with 4 backends (Ollama, MLX, Anthropic, OpenAI)
- [x] Configuration system with YAML + environment overrides
- [x] Demo script with 6 scenarios + interactive mode
- [x] GUI client with terminal aesthetic and real-time visualization
- [x] Comprehensive logging and debugging

**MLX Integration (Critical Upgrade):**
- [x] Switched from Ollama (fake probabilities) to MLX (true logit extraction)
- [x] Implemented extract_logit_probs() with softmax over SAFE/RISK tokens
- [x] Verified calibrated probabilities (not binary 0.0/1.0)
- [x] Added 6 few-shot examples to both Stage 1 and Stage 2
- [x] Enhanced system prompts (1224 chars Stage 1, 1600 chars Stage 2)
- [x] Fixed config extraction for few_shot and system_prompt
- [x] Fixed any_risk_in_buffer flag connectivity in GUI
- [x] Added comprehensive FLOW logging for debugging

### Active Bugs 🔴

**GUI Metadata Crash**:
- Logs stop at "Building metadata" (app.py:303)
- Never reaches "Added user message" (app.py:336)
- Silent failure prevents UI updates
- Backend processing completes successfully
- **Impact**: GUI completely non-functional despite working backend

**Gradio Event Batching**:
- User types 88 chars, only 15 datapoints show in chart
- Gradio batches rapid keystrokes into single events
- on_user_type() adds one entry per event, not per character
- **Impact**: Incomplete visualization, but backend unaffected

### Next Steps (Prioritized)
1. **Fix GUI metadata crash** - Critical blocker for any GUI use
2. **Fix or document Gradio batching** - Decide on architectural approach
3. **Model enum restructure** - Clarify which models support logit extraction
4. **Integration tests** - Validate MLX backend end-to-end
5. **Documentation updates** - Reflect current status and known issues
6. **Phase 3**: Begin synthetic data generation once GUI stabilized
