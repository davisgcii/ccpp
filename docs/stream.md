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
self.pending_classifications = []   # Queue: [(space_pos, text, conversation)]
self.lock = RLock()                 # Protects all state access
```

### Method: `should_process_buffer()` (lines 136-178)

Called by timer to check if stream break should trigger.

```
RETURNS FALSE IF:
├── is_processing == True           "Already processing, returning False"
├── buffer == ""                    "No buffer, returning False"
├── is_classifying == True          "Classification in progress, returning False"
├── pending_classifications != []   "Pending classifications, returning False"  ← NEW
├── buffer == processed_buffer      "Buffer already processed, returning False"
├── last_input_time == None         "No last_input_time, returning False"
└── elapsed < stream_break_timeout  "elapsed=Xs, timeout=2.0s, should_process=False"

RETURNS TRUE IF:
└── elapsed >= stream_break_timeout "elapsed=Xs, timeout=2.0s, should_process=True"
```

**Note**: The `pending_classifications` check ensures stream break waits for all queued classifications to complete.

---

## File: `src/ccpp/gui/app.py`

### Function: `on_user_type()` - FAST, NON-BLOCKING

Triggered by Gradio on every keystroke. Now returns immediately after queuing work.

```
FLOW:
1. Acquire state.lock
2. Update state.buffer = user_input
3. Update state.last_input_time = time.time()
4. If buffer empty → clear history, return
5. Find all NEW spaces since last queued position
6. Queue classifications to pending_classifications
7. Generate UI components (risk_html, chart)
8. Release lock, return
```

**Key improvement**: No blocking classification calls. Handler returns in ~10ms.

### Function: `process_pending_classifications()` - PROCESSES QUEUE

Called by timer_tick to process ONE classification from the queue.

```
FLOW:
1. Acquire lock, pop first item from pending_classifications
2. Release lock
3. Run classification (~2.5s, lock NOT held)
4. Acquire lock, apply results if buffer still valid
5. Release lock, return
```

### Function: `timer_tick()` - MAIN TIMER HANDLER

Called every 500ms. Processes classifications then checks for stream break.

```
FLOW:
1. Call process_pending_classifications()
2. If classification was processed → return (update UI)
3. Else call check_and_process_buffer() for stream break check
```

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

### Gradio Event Wiring

```python
# User typing - fires on every character change (FAST, non-blocking)
current_display.input(
    fn=lambda text: on_user_type(text, state),
    inputs=current_display,
    outputs=[user_input_hidden, risk_indicators, risk_chart, status],
)

# Timer - fires every 0.5s (processes classifications + stream break)
timer = gr.Timer(value=0.5)
timer.tick(
    fn=lambda: timer_tick(state),  # Calls process_pending_classifications + check_and_process_buffer
    outputs=[conversation_history, current_display, ...],
)
```

---

## Historical: Race Condition (Fixed)

For context, this describes the race condition that existed before the queue-based architecture was adopted.

### Timeline of the Bug

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

### Root Cause

1. **Lock held too long**: `on_user_type` held the lock during ALL sequential classifications (10+ seconds)

2. **Events queue up**: During lock hold, both timer ticks AND user keystrokes queued up waiting for lock

3. **Race on release**: When lock was released, timer and keystroke events raced. Timer could win.

4. **Stale buffer**: Timer processed whatever was in buffer when `on_user_type` started (not the user's current input)

5. **Lost input**: User typed "hi i'm trying to find where my order is thanks" but only "hi i'm trying to find w" was in the buffer when stream break fired. The rest was in queued events that never got a chance to run.

Resolved by the queue-based architecture described below.

---

## State Machine

```
┌──────────┐    keystroke    ┌──────────────┐
│  IDLE    │ ──────────────► │   TYPING     │ (on_user_type queues work)
│          │                 │              │
└──────────┘                 └──────┬───────┘
     ▲                              │
     │                              │ space detected → queue classification
     │                              │ (returns immediately, no blocking!)
     │                              ▼
     │                       ┌──────────────┐
     │                       │   TYPING     │ (pending_classifications > 0)
     │                       │  (queued)    │
     │                       └──────┬───────┘
     │                              │
     │                              │ timer tick (every 500ms)
     │                              ▼
     │                       ┌──────────────┐
     │                       │ CLASSIFYING  │ (process ONE from queue)
     │                       │   (2-3s)     │ (doesn't block keystrokes)
     │                       └──────┬───────┘
     │                              │
     │                              │ done → apply result
     │                              │ → next tick continues queue
     │                              ▼
     │                       ┌──────────────┐
     │    more keystrokes    │   TYPING     │
     │    ◄────────────────  │  (updated)   │
     │    (captured!)        └──────┬───────┘
     │                              │
     │                              │ queue empty + 3s timeout
     │                              ▼
     │                       ┌──────────────┐
     │                       │STREAM BREAK  │ (all words classified!)
     │                       │ DETECTED     │
     │                       └──────┬───────┘
     │                              │
     │                              ▼
     │                       ┌──────────────┐
     │                       │ PROCESSING   │ (Stage 2 + Anthropic)
     │                       │              │
     │                       └──────┬───────┘
     │                              │
     │                              │ done, input cleared
     └──────────────────────────────┘
```

**Key improvement**: Keystrokes are never blocked. The queue ensures all words get classified before stream break.

---

## Key Metrics from Logs

| Operation | Typical Duration |
|-----------|------------------|
| Single classification (MLX) | 2,400 - 2,500 ms |
| Anthropic API call | 1,200 - 1,400 ms |
| Timer tick interval | 500 ms |
| Stream break timeout | 2,000 ms |

**Implication**: If user types 4 words quickly, classification takes ~10s. Timer will definitely fire before classifications complete, but it's blocked. When lock releases, timer has been waiting 7+ seconds and will immediately trigger stream break.

---

## Fix Applied

### Solution: Queue-Based Classification (Non-Blocking Handler)

The architecture was restructured to use a classification queue:

1. **`on_user_type()`** is now fast and non-blocking - it only queues work
2. **`timer_tick()`** processes ONE classification per tick (every 500ms)
3. **`should_process_buffer()`** blocks stream break while queue is non-empty

```
on_user_type() - FAST, NON-BLOCKING:
├── Update state.buffer = user_input
├── Update state.last_input_time
├── Find NEW space positions since last queued
├── Queue classifications to pending_classifications
└── Return immediately (no blocking!)

timer_tick() - CALLED EVERY 500ms:
├── If pending_classifications not empty:
│   ├── Pop ONE classification from queue
│   ├── Run classification (2.5s, but doesn't block events)
│   ├── Apply result to state
│   └── Return (let next tick continue)
└── Else check for stream break:
    └── Call check_and_process_buffer()

should_process_buffer() - STREAM BREAK GATING:
├── Return False if is_processing
├── Return False if buffer empty
├── Return False if is_classifying
├── Return False if pending_classifications not empty  ← NEW
├── Return False if buffer already processed
├── Return False if timeout not reached
└── Return True (trigger stream break)
```

### Key Changes

1. **Handler never blocks**: `on_user_type` returns immediately after queuing
2. **All keystrokes captured**: Gradio events don't pile up waiting for lock
3. **Stream break waits for queue**: Won't fire until all words classified
4. **Timer drives classification**: One classification per 500ms tick

### New Timeline (After Fix)

```
00:45:46.396  on_user_type receives "hi " → queues pos=2, returns immediately
00:45:46.450  on_user_type receives "hi i" → no new space, returns
00:45:46.500  on_user_type receives "hi i'm " → queues pos=6, returns
00:45:46.550  Timer tick → starts classifying pos=2
00:45:46.600  on_user_type receives "hi i'm trying " → queues pos=13, returns
...keystrokes continue, all captured...
00:45:49.050  Timer tick → classification for pos=2 done, applies result
00:45:49.550  Timer tick → starts classifying pos=6
...timer processes queue one at a time...
00:46:05.000  User stops typing
00:46:08.000  Timer tick → queue empty, elapsed > 2s
             Stream break fires with COMPLETE buffer
```

### State Variables Added

```python
# In PIIClientState.__init__():
self.pending_classifications: list[tuple[int, str, list]] = []
# Each entry: (space_position, text_to_classify, conversation_snapshot)
```

---

## Remaining Considerations

1. **Classification ordering**: Queue is FIFO, so classifications happen in order of spaces detected.

2. **Buffer changes during classification**: If user deletes text, stale classifications are skipped when their result would be applied.

3. **Chart reset**: `archived_risk_history` is now cleared at stream break so the chart resets between messages.

The fundamental issue (blocking handler causing event coalescing) is now resolved.
