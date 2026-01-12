# Streaming Architecture Analysis

This document traces the complete flow of user input through the PII masking system, identifying all components involved in buffering, classification, and stream break detection.

## Overview

The system has three main event sources running concurrently:
1. **User typing** → `on_user_type()` in `app.py`
2. **Timer tick** (every 0.5s) → `check_and_process_buffer()` in `app.py`
3. **Classification** (blocking, 2-3s each) → `stage1.classify()` via MLX backend

All three interact through shared state protected by a single `RLock`.

---

## File: `src/ccpp/gui/state.py`

### Class: `PIIClientState`

Core state variables for streaming:

```python
self.buffer = ""                    # Current user input text
self.last_input_time = None         # Timestamp of last keystroke
self.processed_buffer = ""          # Buffer text when last sent to LLM
self.is_processing = False          # True while calling Anthropic API
self.is_classifying = False         # True while running Stage 1 classification
self.last_classified_len = 0        # Length of buffer at last classification
self.lock = RLock()                 # Protects all state access
```

### Method: `should_process_buffer()` (lines 136-178)

Called by timer to check if stream break should trigger.

```
RETURNS FALSE IF:
├── is_processing == True           "Already processing, returning False"
├── buffer == ""                    "No buffer, returning False"
├── is_classifying == True          "Classification in progress, returning False"
├── buffer == processed_buffer      "Buffer already processed, returning False"
├── last_input_time == None         "No last_input_time, returning False"
└── elapsed < stream_break_timeout  "elapsed=Xs, timeout=3.0s, should_process=False"

RETURNS TRUE IF:
└── elapsed >= stream_break_timeout "elapsed=Xs, timeout=3.0s, should_process=True"
```

**Critical issue**: This method acquires the lock. If `on_user_type` holds the lock (during classification), this blocks until lock is released.

---

## File: `src/ccpp/gui/app.py`

### Function: `on_user_type()` (lines 106-257)

Triggered by Gradio on every keystroke (batched).

```
FLOW:
1. Acquire state.lock                           # BLOCKS if held elsewhere
2. Update state.buffer = user_input
3. Update state.last_input_time = time.time()
4. If buffer empty → clear history, return
5. Find all NEW spaces since last_classified_len
6. For EACH new space position:                 # SEQUENTIAL, each ~2-3s
   a. state.is_classifying = True
   b. risk_score = state.stage1.classify(...)   # BLOCKING CALL (~2-3s)
   c. state.is_classifying = False
   d. Update EMA, risk_history
7. Update last_classified_len
8. Generate UI components (risk_html, chart)
9. Release lock (implicit on return)
10. Return updated UI
```

**Critical issue**: Lock is held for ENTIRE duration of step 6 loop. If user typed 4 spaces, this holds the lock for ~10-12 seconds while all 4 classifications run sequentially.

### Function: `check_and_process_buffer()` (lines 260-478)

Called by timer every 0.5s.

```
FLOW:
1. Call state.should_process_buffer()           # Acquires lock internally
2. If False → return gr.update() (no changes)
3. If True → STREAM BREAK DETECTED
4. Acquire state.lock
5. state.is_processing = True
6. Get original_text = state.buffer
7. If unclassified text at end:                 # NEW: handles no trailing space
   a. state.is_classifying = True
   b. Run final classification
   c. state.is_classifying = False
8. Check if should_mask (any_risk, EMA, heuristics)
9. If should_mask → call Stage 2 redactor
10. Mark state.processed_buffer = state.buffer
11. Add user message to conversation
12. Archive risk_history
13. Clear current_char_data, risk_history
14. Reset last_classified_len = 0
15. Release lock
16. Call Anthropic API (outside lock)           # ~1-2s
17. Add assistant response to conversation
18. Clear input textbox (return "")
19. Return UI updates
```

### Gradio Event Wiring (lines 601-616)

```python
# User typing - fires on every character change
current_display.input(
    fn=lambda text: on_user_type(text, state),
    inputs=current_display,
    outputs=[user_input_hidden, risk_indicators, risk_chart, status],
)

# Timer - fires every 0.5s
timer = gr.Timer(value=0.5)
timer.tick(
    fn=lambda: check_and_process_buffer(state),
    outputs=[conversation_history, current_display, ...],
)
```

---

## Race Condition Analysis

### Timeline of the Bug

Based on the logs provided:

```
00:45:46.396  on_user_type receives "hi " (3 chars)
             Lock acquired, classification starts for "hi "

00:45:46.457  Timer tick - BLOCKED waiting for lock

00:45:48.885  Classification done for "hi "
             (User typed more during this 2.5s, but events queued)

00:45:48.926  on_user_type receives "hi i'm trying to find w" (23 chars)
             This is a BATCHED event - Gradio accumulated keystrokes
             Lock acquired, 4 classifications start (positions 6, 13, 16, 21)

00:45:48.956  Timer tick - BLOCKED waiting for lock

00:45:51.385  Classification 1 done (position 6)
00:45:53.839  Classification 2 done (position 13)
00:45:56.319  Classification 3 done (position 16)
00:46:00.467  Classification 4 done (position 21)
             Lock released

00:46:00.468  RACE CONDITION - who gets the lock?
             - Blocked timer tick(s) waiting
             - Blocked on_user_type events with newer text waiting

             TIMER WINS THE RACE!
             should_process_buffer sees elapsed=11.54s > 3s
             STREAM BREAK fires with STALE buffer "hi i'm trying to find w"

00:46:00.469  Buffer cleared, input textbox cleared
             User's additional keystrokes (after "w") are LOST
```

### The Problem

1. **Lock held too long**: `on_user_type` holds the lock during ALL sequential classifications (10+ seconds)

2. **Events queue up**: During lock hold, both timer ticks AND user keystrokes queue up waiting for lock

3. **Race on release**: When lock is released, timer and keystroke events race. Timer can win.

4. **Stale buffer**: Timer processes whatever was in buffer when `on_user_type` started (not the user's current input)

5. **Lost input**: User typed "hi i'm trying to find where my order is thanks" but only "hi i'm trying to find w" was in the buffer when stream break fired. The rest was in queued events that never got a chance to run.

---

## Proposed Fixes

### Option A: Release Lock During Classification

```python
def on_user_type(current_text: str, state: PIIClientState):
    with state.lock:
        state.buffer = user_input
        state.last_input_time = time.time()
        # ... find spaces ...
        spaces_to_classify = [...]

    # Release lock, then classify (allow other events to update buffer)
    for space_pos in spaces_to_classify:
        with state.lock:
            state.is_classifying = True
        try:
            risk_score = state.stage1.classify(...)
        finally:
            with state.lock:
                state.is_classifying = False
                # ... update risk history ...

    with state.lock:
        # ... generate UI ...
```

**Problem**: Buffer might change between classifications, making results inconsistent.

### Option B: Snapshot Buffer, Don't Block New Input

```python
def on_user_type(current_text: str, state: PIIClientState):
    with state.lock:
        state.buffer = user_input
        state.last_input_time = time.time()
        snapshot = user_input  # Work on snapshot
        spaces_to_classify = [...]

    # Classify snapshot without holding lock
    results = []
    for space_pos in spaces_to_classify:
        risk_score = state.stage1.classify(state.conversation, snapshot[:space_pos+1])
        results.append((space_pos, risk_score))

    with state.lock:
        # Only apply results if buffer hasn't changed too much
        if state.buffer.startswith(snapshot):
            for space_pos, risk_score in results:
                # ... update risk history ...
```

### Option C: Async Classification with Queue

Move classification to a background thread/queue:

```python
# In on_user_type:
with state.lock:
    state.buffer = user_input
    state.last_input_time = time.time()
    state.classification_queue.put((user_input, space_positions))

# Background worker:
while True:
    text, positions = classification_queue.get()
    for pos in positions:
        result = stage1.classify(text[:pos+1])
        with state.lock:
            if state.buffer.startswith(text[:pos+1]):
                state.risk_history.append(...)
```

### Option D: Defer Stream Break Until Stable

Don't trigger stream break if there are pending events:

```python
def should_process_buffer(self) -> bool:
    with self.lock:
        # ... existing checks ...

        # NEW: Don't process if classification was recent
        # (more keystrokes might be queued)
        if self.last_classification_time and \
           time.time() - self.last_classification_time < 0.5:
            return False
```

---

## Current State Machine

```
                    ┌─────────────────────────────────────────────────┐
                    │                                                 │
                    ▼                                                 │
┌──────────┐    keystroke    ┌──────────────┐                        │
│  IDLE    │ ──────────────► │   TYPING     │                        │
│          │                 │              │                        │
└──────────┘                 └──────┬───────┘                        │
     ▲                              │                                │
     │                              │ space detected                 │
     │                              ▼                                │
     │                       ┌──────────────┐                        │
     │                       │ CLASSIFYING  │ (is_classifying=True)  │
     │                       │   (2-3s)     │ LOCK HELD              │
     │                       └──────┬───────┘                        │
     │                              │                                │
     │                              │ done                           │
     │                              ▼                                │
     │                       ┌──────────────┐                        │
     │                       │   TYPING     │                        │
     │                       │  (updated)   │                        │
     │                       └──────┬───────┘                        │
     │                              │                                │
     │         3s timeout           │ more spaces?                   │
     │         (timer wins race)    │                                │
     │              │               ▼                                │
     │              │        ┌──────────────┐                        │
     │              │        │ CLASSIFYING  │ (loop continues)       │
     │              │        └──────────────┘                        │
     │              │               │                                │
     │              ▼               │ all spaces done                │
     │       ┌──────────────┐       │                                │
     │       │STREAM BREAK  │◄──────┘ (lock released, timer wins)    │
     │       │ DETECTED     │                                        │
     │       └──────┬───────┘                                        │
     │              │                                                │
     │              ▼                                                │
     │       ┌──────────────┐                                        │
     │       │ PROCESSING   │ (is_processing=True)                   │
     │       │ (Stage 2 +   │                                        │
     │       │  Anthropic)  │                                        │
     │       └──────┬───────┘                                        │
     │              │                                                │
     │              │ done, input cleared                            │
     └──────────────┘                                                │
                    │                                                │
                    │ (queued keystrokes finally run,                │
                    │  but input was cleared - INPUT LOST!)          │
                    └────────────────────────────────────────────────┘
```

---

## Key Metrics from Logs

| Operation | Typical Duration |
|-----------|------------------|
| Single classification (MLX) | 2,400 - 2,500 ms |
| Anthropic API call | 1,200 - 1,400 ms |
| Timer tick interval | 500 ms |
| Stream break timeout | 3,000 ms |

**Implication**: If user types 4 words quickly, classification takes ~10s. Timer will definitely fire before classifications complete, but it's blocked. When lock releases, timer has been waiting 7+ seconds and will immediately trigger stream break.

---

## Fix Applied

### Solution: Release Lock During Classification (Option B)

The `on_user_type()` function was restructured into three phases:

```
PHASE 1: Update buffer (LOCK HELD - brief)
├── Update state.buffer = user_input
├── Update state.last_input_time
├── Find space positions to classify
├── Snapshot conversation
├── Set is_classifying = True
└── RELEASE LOCK

PHASE 2: Run classifications (LOCK NOT HELD)
├── For each space position:
│   └── risk_score = stage1.classify(snapshot, text)
└── Collect results in list

PHASE 3: Apply results (LOCK HELD - brief)
├── Set is_classifying = False
├── Check if buffer still valid (not deleted/changed)
├── Apply classification results to state
├── Update last_classified_len
├── Generate UI components
└── Return current buffer state
```

### Key Changes

1. **Lock hold time reduced from 10+ seconds to ~10ms**
2. **Other events can update buffer during classification**
3. **Stale results are discarded** if buffer changed incompatibly
4. **Stream break can check is_classifying** which is set atomically

### New Timeline (After Fix)

```
00:45:46.396  on_user_type receives "hi " (3 chars)
             Lock acquired, buffer updated, lock released
             Classification starts WITHOUT lock

00:45:46.450  User types more - on_user_type receives "hi i"
             Lock acquired, buffer updated to "hi i", lock released
             No new spaces, returns immediately

00:45:46.500  User types more - on_user_type receives "hi i'm "
             Lock acquired, buffer updated, lock released
             Classification starts for new space

00:45:48.885  First classification done, results applied

...classifications proceed, user can keep typing...

00:46:00.468  Timer tick checks should_process_buffer
             is_classifying = False
             elapsed > 3s since LAST keystroke
             Buffer contains FULL user input
             Stream break fires with COMPLETE buffer
```

---

## Remaining Considerations

1. **Classification ordering**: Multiple concurrent on_user_type events could finish out of order. The `last_classified_len = max(...)` logic handles this.

2. **Buffer prefix check**: If user deletes text during classification, results are discarded. This is correct behavior.

3. **EMA accumulation**: EMA updates happen in Phase 3 under lock, so they're still atomic and ordered.

The fundamental issue (lock held during blocking classification) is now resolved.
