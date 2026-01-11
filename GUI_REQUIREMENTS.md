# GUI Requirements - Updated Design

## Overview
Professional, clean GUI for real-time PII masking with interactive debugging capabilities.

## Layout: Three Vertically Stacked Sections

### 1. Top Section: Conversation History (Scrollable)

**Visual Pattern** (repeats for each exchange):
```
User: I need to get my order, my name is [PII/DIRECT].
Risk: ·············································x·x·x·x·x··x·x·x·x·
EMA:  xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Interactive Hover Tooltips:**
- Hover over any character to see popup with:
  1. **Classifier Prompt**: Full formatted prompt sent to Stage 1 for that character
  2. **Classifier Response**: P(RISK) score and logit probabilities
  3. **Masker Prompt**: Full formatted prompt sent to Stage 2 for that buffer/chunk
  4. **Masker Response**: Entity extractions (e.g., `MASK "george davis" pii/direct`)
  5. **Unredacted Text**: Original character or full buffer before masking

**Flattened Chart**:
- 1-2 line compact visualization aligned with text (monospace)
- Risk line: `·` for P(RISK) < 0.7, `x` for P(RISK) ≥ 0.7
- EMA line: `x` characters, color changes when crossing thresholds

**Visual Hierarchy**:
- User messages: muted blue-gray (#7B9FB5)
- Assistant messages: muted gray (#999)
- Risk/EMA indicators: color-coded (blue/green/red/orange)
- Scrollable, takes up ~30-40% of vertical space

**After Assistant Response:**
```
Assistant: Order Lookup

I'd be happy to help you find your order! However, I don't have access to order
management systems or customer databases.
```

---

### 2. Middle Section: Active I/O

**Current Input** (as you type):
```
I need to get my order, my name is george davis.
^cursor
```

**Streamed Response** (as assistant responds):
```
Order Lookup

I'd be happy to help...
```

**Behavior**:
- Shows exactly what you're typing (bright colors)
- Shows exactly what assistant is responding (bright colors)
- Does NOT show masked version (masked version only appears in history)
- After 3-second pause detected:
  - Content moves up to Top Section (conversation history)
  - Middle section resets/clears
  - Ready for next input

**Interruption**:
- If user types during assistant response:
  - Response immediately pauses
  - Only displayed portion is saved to history
  - Cursor returns to input
  - Timer resets

---

### 3. Bottom Section: Full Chart

**Real-time Metrics Chart** (aligned with middle section text):
```
RISK and EMA

│
│    x                                    xxx  x xx
│   x                                    x   xx  x
│  x                                    x
├──────────────────────────────────────────────────── T_high (EMA escalation)
│ x
│x
├─────────────────────────────────────────────────────T_low (EMA de-escalation)
│····························································
└────────────────────────────────────────────────────────────

· RISK=0.850  x EMA=0.620
```

**Features**:
- Full-width ASCII art chart
- Two overlaid series:
  - `·` for P(RISK) per character (blue #5B9BD5)
  - `x` for EMA (green #90ee90 when safe, red #ff6b6b when ≥ T_high)
- Horizontal threshold lines:
  - T_high (orange #FFA500)
  - T_low (gray #666)
- Character-aligned with middle section text (monospace font)
- Real-time updates as you type
- Current values displayed below

---

## Data Storage Requirements

To support interactive hover tooltips, we need to store comprehensive metadata for each exchange.

### Per-Character Classification Data:
```python
{
    "char": "g",
    "idx": 0,
    "risk_score": 0.55,
    "ema_at_char": 0.12,
    "classifier_prompt": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "Context: ...\nCurrent buffer: g"}
    ],
    "classifier_response": {
        "p_safe": 0.45,
        "p_risk": 0.55,
        "logits": {"SAFE": -0.2, "RISK": 0.1}
    }
}
```

### Per-Buffer Masking Data:
```python
{
    "role": "user",
    "content": "I need to get my order, my name is [PII/DIRECT].",  # Masked
    "metadata": {
        "original": "I need to get my order, my name is george davis.",
        "char_classifications": [
            # Array of per-character data (see above)
            {...}, {...}, ...
        ],
        "risk_history": [
            # Copy of state.risk_history for mini chart
            {"char_idx": 0, "p_risk": 0.1, "ema": 0.1, "any_risk": False},
            ...
        ],
        "masker_prompt": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "Context: ...\nBuffer: george davis"}
        ],
        "masker_response": {
            "raw": "MASK \"george davis\" pii/direct",
            "entities": [{"text": "george davis", "category": "pii/direct"}]
        },
        "heuristic_matches": [
            # Any fast heuristic matches
            {"pattern": "name_pattern", "confidence": 0.85}
        ]
    }
}
```

### State Management Updates:
```python
class PIIClientState:
    # Existing fields...

    # New fields for tooltip data:
    current_char_classifications: list  # Per-char data for current buffer
    current_masker_data: dict           # Masker prompt/response for current buffer
```

---

## Implementation Strategy

### Phase 1: Data Collection
1. Update `on_user_type()` to store full classifier prompt/response per character
2. Update `check_and_process_buffer()` to store masker prompt/response
3. Update `PIIClientState.conversation` to include metadata dict
4. Ensure all data needed for tooltips is captured and stored

### Phase 2: HTML Generation with Tooltips
1. Create `create_hoverable_text()` function:
   - Wraps each character in `<span>` with data attributes
   - Stores tooltip content in HTML data attributes or generates on hover
   - Uses CSS for tooltip styling

2. Update `create_conversation_history_html()`:
   - Generate hoverable spans for user messages
   - Render flattened mini-chart under each message
   - Maintain color coding and visual hierarchy

3. Tooltip content template:
   ```html
   <div class="tooltip">
     <strong>Character '{char}' (index {idx})</strong>

     <div class="section">
       <h4>Classifier (Stage 1)</h4>
       <pre>Prompt: {classifier_prompt}</pre>
       <pre>Response: P(RISK)={risk_score:.3f}</pre>
     </div>

     <div class="section">
       <h4>Masker (Stage 2)</h4>
       <pre>Prompt: {masker_prompt}</pre>
       <pre>Response: {masker_response}</pre>
     </div>

     <div class="section">
       <h4>Original Text</h4>
       <pre>{original_buffer}</pre>
     </div>
   </div>
   ```

### Phase 3: Layout Redesign
1. Remove sidebar layout
2. Create three stacked sections:
   - Top: History (scrollable, max-height with overflow)
   - Middle: Active I/O (fixed height)
   - Bottom: Chart (fixed height)

3. Full-width design with proper spacing

### Phase 4: Chart Alignment
1. Use monospace font throughout (Courier New)
2. Render chart with exact character alignment:
   - Calculate character width
   - Position risk/EMA indicators at exact character positions
   - Ensure text in middle section and chart line up perfectly

### Phase 5: Interaction Flow
1. Typing updates middle section + bottom chart in real-time
2. Stream break (3s pause) triggers:
   - Masking operation
   - Move to history with metadata
   - Clear middle section
   - Reset for next input
3. Hover in history shows tooltip
4. Interruption during assistant response handled gracefully

---

## Color Scheme (Professional & Clean)

**Active Content (Middle Section):**
- Text: bright (#eee)
- Cursor: blinking
- Background: dark (#1a1a1a)

**History (Top Section):**
- User messages: muted blue-gray (#7B9FB5)
- Assistant messages: muted gray (#999)
- Risk indicators: Blue (#5B9BD5) for dots, Red (#ff6b6b) for high risk
- EMA indicators: Green (#90ee90) for safe, Red (#ff6b6b) for escalated
- Background: slightly lighter (#1a1a1a)

**Chart (Bottom Section):**
- Axes: dark gray (#444)
- P(RISK) dots: blue (#5B9BD5)
- EMA line: green (#90ee90) or red (#ff6b6b)
- T_high threshold: orange (#FFA500)
- T_low threshold: gray (#666)
- Background: dark (#0d0d0d)

**Tooltips:**
- Background: dark gray (#2a2a2a)
- Border: light gray (#555)
- Text: white (#eee)
- Code blocks: slightly darker background (#1a1a1a)

---

## Technical Considerations

### Gradio Limitations:
- Gradio HTML components don't support JavaScript-based hover events easily
- Options:
  1. Use CSS-only tooltips with `:hover` pseudoclass
  2. Embed JavaScript in HTML for more complex interactions
  3. Use Gradio's built-in tooltip support (if available)
  4. Custom Gradio component (advanced)

### Performance:
- Storing full prompts/responses per character could get large
- Consider:
  - Circular buffer (keep last N exchanges)
  - Compress/summarize older history
  - Lazy-load tooltip data on hover

### Monospace Alignment:
- Critical for chart alignment
- Must use consistent font-family throughout
- Test on different screen sizes/zoom levels

---

## Success Criteria

1. Three clearly distinct vertical sections
2. History shows user message → mini chart → assistant response pattern
3. Hover over any character shows full debugging info
4. Middle section clears after stream break
5. Chart perfectly aligns with text above (character-by-character)
6. Professional, clean design with smart color usage
7. No confusing duplicate displays of same information
8. Clear visual flow: type → see live metrics → pause → move to history → repeat
