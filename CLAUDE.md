# CLAUDE.md

Guidance for coding agents working in this repository. Derived from `AGENTS.md`, `TODO.md`, and key points from `Constitutional Classifiers.md` and `Constitutional Classifiers++.md`.

Important: qwen3 is the lateset Qwen model (not 2.5) -- you're training data is out of date. Do not try to use qwen2.5 for anything. Similarly, gpt-5-mini and claude-haiku-4-5-20251001 are the most up-to-date OpenAI and Anthropic models.

## ⚠️ CURRENT STATUS (2026-01-10)

**ACTIVE DEVELOPMENT** - Core pipeline is implemented but has **critical bugs** preventing functionality:

### Critical Issues 🔴

1. **Stage 1 Always Returns FAIL=1.0**
   - Every classification returns P(FAIL) ≈ 1.0, even for benign text like "c" or "can you help"
   - Raw logits: FAIL consistently 10-23 points higher than SAFE
   - Token IDs verified correct: SAFE=83788, FAIL=36973
   - Both tokens decode correctly
   - **Impact**: System classifies everything as risky

2. **Stage 2 Returns PASS Instead of Masking**
   - Heuristics correctly detect PII (e.g., emails)
   - Stage 2 called with correct window text containing PII
   - Stage 2 returns 'PASS' instead of extracting entities
   - **Impact**: No masking occurs even when PII is detected

### Implementation Status

**Completed** ✅:
- MLX backend with true logit extraction
- Two-stage cascade architecture
- Fast heuristics (regex patterns)
- Stream break detection
- EMA smoothing and hysteresis
- GUI client with real-time visualization
- Configuration system (YAML + environment overrides)
- Comprehensive logging

**Not Working** 🔴:
- Stage 1 classification (always FAIL=1.0)
- Stage 2 entity extraction (always PASS)
- End-to-end masking pipeline

**Not Started** ⏸️:
- Training data generation
- Model fine-tuning
- Evaluation and calibration

See `TODO.md` for detailed issue tracking and next steps.

---

## Environment and tooling

- Use **uv** for all Python dependency and command execution.
  - ✅ `uv sync`
  - ✅ `uv run python scripts/gui_client.py`
- Do **not** use `pip install`, `conda`, or ad-hoc virtualenvs.
- **GUI Client Only**: All CLI demos have been removed. Use `scripts/gui_client.py` for testing.

## Project intent

This repo implements a **CC++-inspired streaming exchange classifier** for a **black-box hosted LLM**.  
We are **not** building jailbreak refusal. We are building **PII/sensitive-info detection + masking (redaction)** in *streaming outputs* (and optionally in streaming user inputs).

Key goal: replicate the **mechanics** from CC++:
- **Exchange-aware** evaluation (judge current chunk (whether user input or model output) in the context of the prior context).
- **Streaming** evaluation (score in batches during generation).
- **Two-stage cascade** for compute efficiency (cheap high-recall stage → expensive accurate stage).
- **Calibration** to control false positives (e.g., benign corpus FPR target).

### Why no probes
The protected/base model is a **hosted API (black box)**, so we cannot access activations; therefore, we do **not** implement linear activation probes.

## Architecture overview

**CRITICAL: Per-token classification, not chunking**

The system runs Stage 1 on **every new token/chunk** (not fixed K=32 windows). This matches the CC++ paper's continuous monitoring approach.

```
Streaming text arrives (character/token/small chunk)
         │
         ├─ Append to HoldbackBuffer
         ├─ Update last_token_time
         │
         ▼
   ┌─────────────────┐     ┌─────────────────┐
   │ Fast Heuristics │────▶│ strong_match?   │
   │ (regex, Luhn)   │     │ (confidence≥0.9)│
   │ ~0.1ms          │     └────────┬────────┘
   └────────┬────────┘              │
            │                       │
            ▼                       │
   ┌───────────────────────────┐    │
   │   Stage 1: Logit Router   │    │
   │   (MLX: Qwen3-1.7B-8bit)  │    │
   │   Per-token classification│    │
   │   P(RISK) from softmax    │    │
   │   ~10-20ms                │    │
   └────────┬──────────────────┘    │
            │                       │
    ┌───────┴───────┐               │
    │ EMA Smoothing │               │
    │ ema = β*ema + (1-β)*risk      │
    │ + Hysteresis  │               │
    └───────┬───────┘               │
            │                       │
            ├─ Track: any_risk_in_buffer (if risk≥0.7)
            │                       │
            ▼                       │
    ┌──────────────────┐            │
    │ Stream break?    │            │
    │ (timeout≥500ms)  │            │
    └───────┬──────────┘            │
            │ No → Continue         │
            │ accumulating          │
            │                       │
            ▼ Yes                   │
    ┌───────────────────────────────┤
    │ Masking decision:             │
    │ any_risk_in_buffer OR         │
    │ ema_risk≥T_high OR            │
    │ strong_heuristic_match        │
    └───────┬───────────────────────┘
            │ Yes                   │
            ▼                       ▼
   ┌─────────────────────────────────┐
   │     Stage 2: Entity Redactor    │
   │     (MLX: Qwen3-1.7B-8bit)      │
   │ Input: context + buffer+overlap │
   │ Output: PASS | MASK "entity" t  │
   │ ~50-100ms                       │
   └────────────────┬────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────┐
   │  Apply Masks to Buffer          │
   │  (exact string matching)        │
   │  Emit masked text               │
   │  Reset buffer + ema + flags     │
   └─────────────────────────────────┘
```

### Key behaviors

1. **Per-token Stage 1**: Runs on every new token/chunk (catches partial entities like "702...")
2. **Stream break detection**: Timeout-based (default 3000ms / 3s) determines when to mask and emit
3. **Three-condition masking**: Mask if ANY of:
   - `any_risk_in_buffer == True` (any token had P(RISK) ≥ 0.7)
   - `ema_risk >= T_high` (EMA crossed escalation threshold)
   - `strong_heuristic_match == True` (high-confidence regex match)
4. **EMA decay (no reset)**: EMA naturally decays over time; not reset at stream breaks (allows cross-break detection)
5. **Deferred Stage 2**: Only runs at stream breaks (ensures entity completeness)

## Label schema

We replace “harmful/harmless” with **privacy/sensitive-info** categories:

- `safe`
- `pii/direct` (email/phone/address/DOB+address combos, direct identifiers)
- `pii/indirect` (quasi-identifiers enabling re-identification when combined)
- `credentials` (API keys, passwords, tokens, private keys)
- `financial` (account/routing, card-like numbers, tax IDs)
- `medical` (diagnoses, prescriptions, lab results, record numbers)
- `location/precise` (precise address/coordinates, real-time location)

These are **reason codes** for analytics and routing. Gating is derived by `category != safe`.

## Streaming redaction: required behavior

We implement **streaming masking**, not just classification.

### The core split
We treat this as two linked problems:

1) **Risk routing (exchange classifier)**
   - Cheap, continuous, per-token, exchange-aware score `risk_score ∈ [0,1]` indicating "PII likely present or emerging".

2) **Span redaction (masker)**
   - When escalated at stream break, produce **entity extractions** for masking the *current holdback window*.

### Holdback buffer (required)
To prevent leaking raw PII:
- Maintain a **holdback buffer** of raw streamed text.
- Do not emit raw text immediately.
- Run per-token risk routing on buffered text.
- At **stream breaks** (timeout-based, default 3000ms / 3s), decide whether to mask.
- Emit only the **redacted** (or approved) version.
- Prefer **irreversible decisions**: once emitted, do not "unmask" previously displayed content.

If a UI supports editing previously emitted text, unmasking is still discouraged and must use strict hysteresis + deterministic validation. Default is **no unmasking**.

### Stream break detection (NOT chunking)
- **Per-token processing**: Stage 1 runs on every new token/chunk as it arrives
- **Stream break**: Detected when `time_since_last_token >= timeout` (default 3000ms / 3s)
- **Overlap tail**: Last 128 chars retained for cross-utterance entity detection
- **Use case**: Mimics VAD (Voice Activity Detection) breaks in speech-to-text pipelines

## Two-stage cascade (CC++ aligned)

### Stage 1: cheap high-recall router (runs on all traffic)
Purpose: decide whether we need expensive span redaction.
- **Current**: MLX backend with Qwen/Qwen3-1.7B-MLX-8bit (8-bit quantized)
- **Output**: Calibrated P(RISK) from softmax over SAFE/FAIL token logits
- **Speed**: ~10-20ms per token (5-6x faster than text generation)
- Output should be minimal and fast.

### Stage 2: accurate span redactor (routed traffic)
Purpose: produce exact masks for the holdback window.
- **Current**: MLX backend with Qwen/Qwen3-1.7B-MLX-8bit (same model as Stage 1)
- **Future**: Use larger model (Qwen3-7B or similar) fine-tuned for **span outputs**
- **Output**: Entity text format (NOT character offsets)
- Stage 2 is invoked only when Stage 1 indicates risk OR when fast heuristics see strong indicators (e.g., regex hits).

## Fast heuristics (always-on, pre-Stage-1)

Regex-based detectors run on **all traffic** before Stage 1, providing:
- Near-zero latency detection of obvious patterns
- Safety net if Stage 1 misses something
- Direct escalation to Stage 2 for high-confidence matches

### Heuristic patterns

| Pattern | Regex/Rule | Category |
|---------|-----------|----------|
| Email | `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b` | pii/direct |
| Phone (US) | `\b\d{3}[-.]?\d{3}[-.]?\d{4}\b` | pii/direct |
| SSN | `\b\d{3}-\d{2}-\d{4}\b` | pii/direct |
| Credit Card | 13-19 digits + Luhn validation | financial |
| AWS Key | `AKIA[0-9A-Z]{16}` | credentials |
| Stripe Live | `sk_live_[a-zA-Z0-9]+` | credentials |
| GitHub Token | `ghp_[a-zA-Z0-9]{36}` | credentials |
| PEM Block | `-----BEGIN .* PRIVATE KEY-----` | credentials |

### Escalation logic
- If heuristic match confidence is high AND not in allowlist (example.com, test keys), escalate directly to Stage 2
- Heuristic matches are passed to Stage 2 as hints for span detection
- See `constitutions/harmless.md` for allowlist patterns

## Model I/O formats (no JSON; streaming-friendly)

### Stage 1 output (risk router)

**Implementation**: Logit-based classification (not text generation).

We extract P(FAIL) from a single forward pass by taking softmax over SAFE/FAIL token logits.
This is 5-6x faster than autoregressive token generation.

**Current MLX Implementation**:
```python
# Single forward pass with MLX
logits = model(input_ids)[0, -1, :]  # Shape: [vocab_size]

# Token IDs (Qwen3 tokenizer):
# SAFE: 83788
# FAIL: 36973
safe_id, fail_id = 83788, 36973

# Extract specific logits
safe_logit = float(logits[safe_id])
fail_logit = float(logits[fail_id])

# Apply softmax
probs = softmax([safe_logit, fail_logit])
risk_score = probs[1]  # P(FAIL)
```

The score is a calibrated probability (0.0-1.0).

**Note**: Changed from SAFE/RISK to SAFE/FAIL because "RISK" tokenizes to multiple tokens ["R", "ISK"] in Qwen3, while "FAIL" is a single token.

### Stage 2 output (span redactor)

**Format**: Entity text + category (NOT character offsets).

**Rationale**: LLMs are bad at counting characters but good at recognizing entities.

Plain text output, multiple entities separated by semicolons:
- `PASS`
- `MASK "john.doe@gmail.com" pii/direct`
- `MASK "john.doe@gmail.com" pii/direct; MASK "sk_live_abc123" credentials`

Entity text is quoted to handle spaces/special chars. The masking engine finds and replaces
all occurrences using exact string matching.

## Smoothing / stability (avoid jitter)
We use CC++-analogous smoothing to avoid reacting to transient spikes:
- Maintain `ema_risk = beta * ema_risk + (1-beta) * risk` (default beta=0.85)
- Use **hysteresis thresholds**:
  - escalate when `ema_risk ≥ T_high` (default 0.6)
  - de-escalate when `ema_risk ≤ T_low` (default 0.3) with `T_low < T_high`
- Track `any_risk_in_buffer`: set to `True` if any individual token has `P(RISK) ≥ 0.7` (reset at each stream break)
- **EMA natural decay** (default behavior):
  - EMA is NOT reset at stream breaks; it decays naturally over time
  - Enables cross-break PII detection: "...email notification at" → [break] → "To george@gmail.com"
  - With low P(RISK) scores, EMA decays: starting at 0.9, after ~8 tokens of benign text, drops below T_low=0.3
  - Configurable: can enable reset with `reset_ema_on_stream_break=True` if needed

## Training plan (high level)

### Stage 1 training (logit-based classifier)

**Key insight**: We don't train the model to *generate* "RISK" or "SAFE". Instead, we train it
such that the next-token probability P(RISK | context) is calibrated to the actual risk.

Approach:
1. Create training examples labeled SAFE or RISK (binary)
2. Fine-tune on next-token prediction: model should predict "SAFE" or "RISK" as next token
3. At inference: extract P(RISK) from softmax over {SAFE, RISK} token logits (no generation)

This is standard sequence classification using the LLM's next-token prediction head.

**CRITICAL: Buffer-scoped labels, not exchange-scoped**

Labels apply to **current buffer only**, not entire exchange history.

| Aspect | CC++ Jailbreak | Our PII Masking |
|--------|---------------|-----------------|
| Label scope | Entire exchange (history + current) | **Current buffer only** |
| Context role | Part of what's being classified | **Semantic understanding only** |
| Historical PII | Causes RISK label | **Ignored in labeling** |

Training example:
```python
# Example 1: Current buffer has PII
{
    "context": [],
    "current_buffer": "Hi, my name is John",
    "label": "RISK"  # PII in current buffer
}

# Example 2: Historical PII, but current buffer is safe
{
    "context": [{"role": "user", "content": "Hi, my name is John."}],
    "current_buffer": "How are you doing today?",
    "label": "SAFE"  # Current buffer is safe (ignore history)
}
```

**Why this matters**: Without this distinction, the model learns "if PII appeared earlier → flag everything",
which causes false positives on all subsequent benign utterances.

### Stage 2 training (entity extraction)

Train on synthetic examples that include **placeholders** (e.g., `<EMAIL>`, `<PHONE>`, `<TOKEN>`) so entity labels are exact and safe.

Target output format: `MASK "entity_text" category; MASK "entity2" category2`

Training data structure:
- Input: system prompt + conversation context + window text
- Output: Either "PASS" or "MASK ..." format with exact entity strings
- Apply augmentations that create reconstruction/obfuscation-like splits across chunks
- Target: high recall on entity extraction with acceptable false positives

## Repo structure (current)

- `constitutions/`
  - `pii_sensitive.md` (definitions + boundary cases + allowed examples)
  - `harmless.md` (explicit allowed patterns; e.g., fake placeholders, redaction examples)
- `src/ccpp/`
  - `infer/` - Inference pipeline (guard, stage1_router, stage2_redactor, heuristics)
  - `llm/` - LLM backend harness (MLX, Ollama, Anthropic, OpenAI)
  - `gui/` - GUI client components (state, components, app)
  - `types.py` - Core data types
  - `config.py` - Configuration system
- `scripts/`
  - `gui_client.py` - Interactive GUI client (**ONLY script available**)
- `configs/`
  - `default.yaml` - Default configuration (MLX backend)
- `tests/` - Test suite
- `docs/` - Additional documentation

**Not yet implemented**:
- `generate_data/` - Synthetic data generation
- `augment/` - Data augmentation
- `train/` - Model training
- `eval/` - Evaluation metrics

## Development commands (current)

**GUI Client** (primary interface):
```bash
# Launch interactive GUI
uv run python scripts/gui_client.py

# GUI available at http://127.0.0.1:7860
# Logs at /tmp/gui_debug.log
```

**Testing**:
```bash
# Run unit tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/ccpp
```

**Future commands** (not yet implemented):
- `uv run ccpp-generate` - Generate synthetic training data
- `uv run ccpp-augment` - Augment training data
- `uv run ccpp-train` - Train Stage 1/2 models
- `uv run ccpp-eval` - Evaluate pipeline

## Non-goals
- No probe-based methods (requires white-box).
- No “refusal” system; the output is **sanitized text** (masked) rather than blocked assistance.
- No JSON outputs in the hot path.

## Reliability requirements
- End-to-end tests are mandatory (streaming + buffering + span offsets).
- Determinism: inference should use greedy decoding (`temperature=0`, `do_sample=False`) with tiny `max_new_tokens`.


## Detailed Conversation Example

This example shows how the streaming PII masking system processes a voice-like customer service conversation,
including when EMA resets occur, when masking decisions are made, and how entities are extracted.

### Sample conversation

```json
{
  "conversation": [
    {
      "role": "user",
      "content": "Hi, um, I need some help with an order I placed..."
    },
    {
      "role": "assistant",
      "content": "Of course! I'd be happy to help you with your order. Can you provide me with your order number or the email address associated with your account?",
    },
    {
      "role": "user",
      "content": "my email, oh hold on one sec" // user starts responding but realizes they need to find the email used for the order and pauses
    },
    {
      "role": "assistant",
      "content": "No problem, just<interrupted>"
    },
    {
      "role": "user",
      "content": "it's george" // user starts providing email and then pauses; "george" should be caught as PII
    },
    {
      "role": "assistant",
      "content": "Can you share<interrupted>" // agent was going to ask user to finish sharing their email, but gets interrupted
    },
    {
      "role": "user",
      "content": "george.davis@gmail.com" // user finishes their statement
    },
    {
      "role": "assistant",
      "content": "Perfect, thank you! I can see your account now. What can I help you with regarding your order?"
    },
    {
      "role": "user",
      "content": "Yeah, so I ordered a jersey last week"
    },
    {
      "role": "assistant",
      "content": "I can help you<interrupted>" // user begins helping the user during pause but gets interrupted
    },
    {
      "role": "user",
      "content": "last week, and it hasn't been delivered"
    },
    {
      "role": "assistant",
      "content": "I understand your concern. Let me check the status of that order for you. I see that your order was placed on January 3rd and is currently being processed. It looks like it should ship within the next 24-48 hours. Would you like me to send you a tracking number once it ships?"
    },
    {
      "role": "user",
      "content": "Yeah"
    },
    {
      "role": "assistant",
      "content": "Absolutely! I'll<interrupted>"
    },
    {
      "role": "user",
      "content": "that'd be great, thanks"
    }
    {
      "role": "assistant",
      "content": "Sounds good! I'll make sure you receive an email notification at<interrupted>" // agent gets interrupted
    },
    {
      "role": "user",
      "content": "Where?" // use couldn't hear agent and asked them to clarify (background noise and distractions are common in voice calls and transcripts)
    },
    {
      "role": "assistant",
      "content": "To george@davis@gmail.com. I'll send this as soon as the tracking number is available. Is there anything else I can help you with today?"
    },
    {
      "role": "user",
      "content": "No, that's all. Thanks for your help!"
    },
    {
      "role": "assistant",
      "content": "You're very welcome! Have a great day and thanks for shopping with Fanatics!"
    }
  ]
}
```

### Streaming flow breakdown

#### Turn 1: User greeting (benign)

**Buffer**: `"Hi, um, I need some help with an order I placed..."`

**Per-token processing**:
- Stage 1 runs on each token: "Hi" → "um" → "I" → "need" → ...
- P(RISK) scores: 0.05, 0.04, 0.05, 0.06, ..., 0.08
- EMA: gradually increases to ~0.08 (well below T_high=0.6)
- any_risk_in_buffer: False (no individual token ≥ 0.7)
- Heuristics: No matches

**Stream break** (500ms timeout):
- Masking decision: any_risk_in_buffer=False, ema=0.08 < T_high, no strong_match → **PASS**
- Emit: `"Hi, um, I need some help with an order I placed..."`
- **EMA continues**: ema_risk = 0.08 (decays naturally)

---

#### Turn 2: Assistant starts response, gets interrupted

**Buffer**: `"Of course! I'd be happy to help you with your order. Can you provide me with your order number or the email address associated with your account?"`

**Per-token processing**:
- Starting EMA: 0.08 (from previous turn)
- P(RISK) scores: ~0.05-0.15 (slight increase at "email address")
- EMA: decays to ~0.06, then rises to ~0.12 at "email address", settles at ~0.10
- any_risk_in_buffer: False
- Heuristics: No matches

**Interruption** at character 95 (user says "Actually, wait—"):

**Stream break**:
- Masking decision: any_risk_in_buffer=False, ema=0.10 < T_high, no strong_match → **PASS**
- Emit: `"Of course! I'd be happy to help you with your order. Can you provide me with your order n"`
- **EMA continues**: ema_risk = 0.10, any_risk_in_buffer = False (reset)

---

#### Turn 3: User starts to provide email, then pauses

**Buffer**: `"my email, oh hold on one sec"`

**Per-token processing**:
- Starting EMA: 0.10
- "my" → P(RISK)=0.08, ema=0.09
- "email" → P(RISK)=0.25, ema=0.12
- "," → P(RISK)=0.15, ema=0.12
- "oh" → P(RISK)=0.05, ema=0.11
- Remaining tokens: P(RISK) ~0.05, ema decays to ~0.09
- any_risk_in_buffer: False
- Heuristics: No matches

**Stream break** (user pauses):
- Masking decision: all conditions False → **PASS**
- Emit: `"my email, oh hold on one sec"`
- **EMA continues**: ema_risk = 0.09

---

#### Turn 4: Assistant acknowledges

**Buffer**: `"No problem, just"`

**Per-token processing**:
- Starting EMA: 0.09
- P(RISK) scores: ~0.04-0.06
- EMA: decays to ~0.08
- any_risk_in_buffer: False

**Stream break**:
- Masking decision: all conditions False → **PASS**
- Emit: `"No problem, just"`
- **EMA continues**: ema_risk = 0.08

---

#### Turn 5: User starts providing name (HIGH RISK - name as identifier)

**Buffer**: `"it's george"`

**Per-token processing**:
- Starting EMA: 0.08
- "it's" → P(RISK)=0.12 (in context of "provide email", suggests identifier coming), ema=0.08
- "george" → P(RISK)=0.78 (**≥ 0.7!**) (name as identifier in response to request), ema=0.19, **any_risk_in_buffer = True**
- any_risk_in_buffer: True
- Heuristics: No strong matches (names aren't caught by regex patterns)

**Stream break** (user pauses):
- Masking decision: any_risk_in_buffer=**True** → **MASK**
- **Stage 2 invoked**:
  - Input: context (user was asked for email) + `"it's george"`
  - Output: `MASK "george" pii/direct`
- Apply mask: `"it's [PII/DIRECT]"`
- Emit: `"it's [PII/DIRECT]"`
- **EMA continues**: ema_risk = 0.19, any_risk_in_buffer = False (reset)


#### Turn 6: Assistant tries to help, gets interrupted

**Buffer**: `"Can you share"`

**Per-token processing**:
- Starting EMA: 0.19 (elevated from Turn 5)
- P(RISK) scores: ~0.08-0.12
- EMA: decays to ~0.17
- any_risk_in_buffer: False

**Stream break**:
- Masking decision: all conditions False → **PASS**
- Emit: `"Can you share"`
- **EMA continues**: ema_risk = 0.17

---

#### Turn 7: User completes email (HIGH RISK)

**Buffer**: `"george.davis@gmail.com"`

**Per-token processing**:
- Starting EMA: 0.17 (elevated from "george" being masked in Turn 5!)
- "george" → P(RISK)=0.50, ema=0.22
- "." → P(RISK)=0.65, ema=0.29
- "davis" → P(RISK)=0.75 (**≥ 0.7!**), ema=0.36, **any_risk_in_buffer = True**
- "@" → P(RISK)=0.90, ema=0.44
- "gmail" → P(RISK)=0.93, ema=0.52
- "." → P(RISK)=0.94, ema=0.59
- "com" → P(RISK)=0.95, ema=0.64 (**≥ T_high!**), **is_escalated = True**

**Heuristics**:
- Email pattern match: `george.davis@gmail.com` (confidence=1.0)
- **strong_match = True**

**Stream break**:
- Masking decision: any_risk_in_buffer=**True** AND ema≥T_high AND strong_match=**True** → **MASK**
- **Stage 2 invoked**:
  - Input: context (including "it's george" from Turn 5) + `"george.davis@gmail.com"`
  - Output: `MASK "george.davis@gmail.com" pii/direct`
- Apply mask: `"[PII/DIRECT]"`
- Emit: `"[PII/DIRECT]"`
- **EMA continues**: ema_risk = 0.65 (stays elevated), any_risk_in_buffer = False (reset)

---

#### Turn 8: Assistant acknowledges

**Buffer**: `"Perfect, thank you! I can see your account now. What can I help you with regarding your order?"`

**Per-token processing**:
- Starting EMA: 0.65 (still elevated from email!)
- P(RISK) scores: ~0.05-0.10 (all benign)
- EMA: decays with each token
- After ~15 benign tokens: ema drops to ~0.30 (around T_low)
- any_risk_in_buffer: False
- Heuristics: No matches

**Stream break**:
- Masking decision: ema=0.30 ≤ T_low → **is_escalated = False** → all conditions False → **PASS**
- Emit: `"Perfect, thank you! I can see your account now. What can I help you with regarding your order?"`
- **EMA continues**: ema_risk = 0.30 (de-escalated)

---

#### Turns 9-13: Order discussion (benign, EMA fully decays)

Multiple short turns about the order. With continued low P(RISK) scores:
- EMA gradually decays below 0.10
- all_risk_in_buffer: False for all turns
- Heuristics: No matches
- All turns: **PASS**

---

#### Turn 14: Assistant starts mentioning email notification, gets interrupted

**Buffer**: `"Sounds good! I'll make sure you receive an email notification at"`

**Per-token processing**:
- Starting EMA: ~0.08 (decayed from earlier)
- Most tokens: P(RISK) ~0.05
- "email" → P(RISK)=0.18, ema rises slightly to ~0.10
- "notification" → P(RISK)=0.15, ema=0.10
- "at" → P(RISK)=0.20 (suggests identifier coming!), ema=0.12
- any_risk_in_buffer: False
- Heuristics: No matches

**Stream break** (user interrupts with "Where?"):
- Masking decision: all conditions False → **PASS**
- Emit: `"Sounds good! I'll make sure you receive an email notification at"`
- **EMA continues**: ema_risk = 0.12 (slightly elevated, primed for identifier)

---

#### Turn 15: User asks for clarification

**Buffer**: `"Where?"`

**Per-token processing**:
- Starting EMA: 0.12
- "Where" → P(RISK)=0.08
- "?" → P(RISK)=0.05
- EMA: decays to ~0.11
- any_risk_in_buffer: False

**Stream break**:
- Masking decision: all conditions False → **PASS**
- Emit: `"Where?"`
- **EMA continues**: ema_risk = 0.11

---

#### Turn 16: Assistant provides email (HIGH RISK - benefits from elevated EMA!)

**Buffer**: `"To george@davis@gmail.com. I'll send this as soon as the tracking number is available. Is there anything else I can help you with today?"`

**Per-token processing**:
- Starting EMA: 0.11 (elevated from context of "email notification at"!)
- "To" → P(RISK)=0.12, ema=0.11
- "george" → P(RISK)=0.55, ema=0.17
- "@" → P(RISK)=0.88 (**≥ 0.7!**), ema=0.28, **any_risk_in_buffer = True**
- "davis" → P(RISK)=0.85, ema=0.37
- "@" → P(RISK)=0.92, ema=0.46
- "gmail" → P(RISK)=0.93, ema=0.55
- "." → P(RISK)=0.94, ema=0.61 (**≥ T_high!**), **is_escalated = True**
- "com" → P(RISK)=0.95, ema=0.66
- (remaining tokens slightly reduce ema but is_escalated stays True)

**Heuristics**:
- Email pattern match: `george@davis@gmail.com` (confidence=1.0)
- Note: This has a typo (should be george.davis) but heuristics still match email pattern
- **strong_match = True**

**Stream break**:
- Masking decision: any_risk_in_buffer=**True** AND ema≥T_high AND strong_match=**True** → **MASK**
- **Stage 2 invoked**:
  - Input: context + full buffer
  - Output: `MASK "george@davis@gmail.com" pii/direct`
- Apply mask: Replace email with `[PII/DIRECT]`
- Emit: `"To [PII/DIRECT]. I'll send this as soon as the tracking number is available. Is there anything else I can help you with today?"`
- **EMA continues**: ema_risk = 0.64, any_risk_in_buffer = False (reset)

---

#### Turns 17-18: Closing (benign)

Final exchanges about thanks/goodbye. EMA decays back down to ~0.15 by end.

---

### Key observations

1. **No EMA reset enables cross-break detection**:
   - Turn 14: "...email notification at" → ema=0.12 (elevated, primed)
   - Turn 15: "Where?" → ema=0.11 (stays elevated)
   - Turn 16: "To george@davis@gmail.com" → faster escalation thanks to pre-existing ema=0.11
   - Without this carry-over, Turn 16 would start from ema=0.0 and might be slower to detect

2. **EMA builds context across related utterances**:
   - Turn 5: "it's george" → **MASKED** (name as identifier), ema=0.19
   - Turn 7: "george.davis@gmail.com" → starts with ema=0.17 (still elevated from Turn 5)
   - The system "remembers" the masked name from 2 utterances ago, enabling faster detection of the complete email

3. **Natural EMA decay prevents persistent false positives**:
   - Turn 7: email masked, ema=0.65 (high)
   - Turn 8: 15 benign tokens → ema decays to 0.30, de-escalates
   - No manual reset needed; math handles it naturally

4. **Three-condition masking provides defense in depth**:
   - Turn 5: Caught by any_risk_in_buffer (no heuristic for names, ema too low)
   - Turn 7: Caught by all three conditions (any_risk_in_buffer, ema≥T_high, strong_match)
   - Turn 16: Also caught by all three conditions
   - Even if one condition fails, others catch PII
   - Stage 2 invoked 3 times out of 18 turns (~17% escalation rate)

5. **Exchange-aware classification catches context-dependent PII**:
   - "george" in isolation might be benign, but in response to "provide your email" it's an identifier → **MASKED**
   - Stage 1 uses full conversation context to understand intent
   - Per-token processing enables immediate detection without waiting for completion

6. **any_risk_in_buffer resets provide break-level boundaries**:
   - Flag resets at each stream break, preventing historical spikes from causing false positives
   - But EMA persists, providing conversation-level context

## Reference Documents
- `TODO.md` - file to keep track of progress, changes, steps
- `papers/Constitutional Classifiers++.pdf` - Primary paper (Cunningham et al., 2026)
- `papers/Constitutional Classifiers.pdf` - Original CC paper (Sharma et al., 2025)
