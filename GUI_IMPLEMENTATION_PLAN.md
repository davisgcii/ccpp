# GUI Implementation Plan - Ultrathink

## Executive Summary

This is a significant architectural redesign requiring:
1. **Data layer changes**: Enhanced metadata storage for debugging tooltips
2. **Presentation layer rewrite**: Three-section vertical layout with hover tooltips
3. **Interaction model shift**: Clear separation between "active" and "history" states

**Complexity**: High
**Estimated effort**: 4-6 hours of focused implementation
**Risk areas**: Gradio tooltip implementation, monospace alignment, performance with large histories

---

## Critical Design Decisions

### 1. Tooltip Implementation Strategy

**Problem**: Gradio doesn't natively support rich hover tooltips with dynamic content.

**Options**:

#### Option A: CSS-Only Tooltips (RECOMMENDED)
```html
<span class="hoverable" data-tooltip="..." data-char="g" data-idx="0">g</span>

<style>
.hoverable {
    position: relative;
    cursor: help;
}

.hoverable:hover::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 100%;
    left: 0;
    background: #2a2a2a;
    border: 1px solid #555;
    padding: 8px;
    white-space: pre-wrap;
    z-index: 1000;
    max-width: 400px;
}
</style>
```

**Pros**:
- No JavaScript required
- Works in Gradio HTML components
- Simple, predictable

**Cons**:
- Limited to `attr()` values (can't use complex HTML)
- All tooltip data must be in HTML attributes (could get large)
- Less flexible styling

#### Option B: JavaScript Tooltips
```html
<span class="hoverable" onclick="showTooltip({idx: 0, data: {...}})">g</span>

<script>
function showTooltip(data) {
    // Create/show tooltip div with rich content
}
</script>
```

**Pros**:
- Full control over tooltip content and styling
- Can lazy-load data
- More interactive possibilities

**Cons**:
- Gradio sanitizes JavaScript in HTML components
- Security restrictions
- More complex

#### Option C: Gradio Custom Component
Build a custom Gradio component with built-in tooltip support.

**Pros**:
- Full control
- Professional implementation
- Reusable

**Cons**:
- Significant development effort (days, not hours)
- Requires React/TypeScript knowledge
- Overkill for this use case

**Decision**: Start with **Option A (CSS-only)** for MVP, consider Option B if needed.

---

### 2. Data Storage Architecture

**Current State Structure**:
```python
class PIIClientState:
    buffer: str
    risk_history: list[dict]  # {char_idx, p_risk, ema, any_risk}
    conversation: list[dict]  # {role, content}
```

**Required State Structure**:
```python
class PIIClientState:
    # Existing
    buffer: str
    conversation: list[dict]  # Enhanced with metadata

    # New: Per-character tracking for current buffer
    current_char_data: list[CharClassification]

    # New: Per-buffer tracking for masking
    current_buffer_data: BufferMetadata

# Data structures
@dataclass
class CharClassification:
    char: str
    idx: int
    risk_score: float
    ema: float
    classifier_prompt: list[dict]  # Full formatted messages
    classifier_response: dict      # {p_safe, p_risk, logits}
    timestamp: float

@dataclass
class BufferMetadata:
    original_text: str
    masked_text: str
    char_data: list[CharClassification]
    masker_prompt: list[dict]
    masker_response: dict  # {raw, entities}
    risk_history: list[dict]  # Copy for mini chart
    heuristic_matches: list[dict]
```

**Enhanced Conversation Structure**:
```python
{
    "role": "user",
    "content": "[PII/DIRECT]",  # Masked version
    "metadata": {
        "original": "george davis",
        "char_data": [CharClassification(...), ...],
        "buffer_data": BufferMetadata(...),
        "timestamp": 1234567890.0
    }
}
```

**Storage Implications**:
- Each character stores ~1-2 KB of metadata (prompts can be large)
- 50-character message = ~50-100 KB
- 10 exchanges = ~500 KB - 1 MB in memory
- **Mitigation**: Implement circular buffer (keep last 20-30 exchanges)

---

### 3. Monospace Alignment Strategy

**Challenge**: Align chart characters with text characters pixel-perfectly.

**Solution**: Strict monospace enforcement + calculated positioning.

```html
<div class="active-input" style="font-family: 'Courier New', monospace; font-size: 14px;">
    I need to get my order, my name is george davis.
</div>

<div class="chart" style="font-family: 'Courier New', monospace; font-size: 14px;">
    ·  ····  ··  ···  ··  ·····   ··  ····  ··  xxxxxx·xxxxxx
</div>
```

**Key Requirements**:
- Same `font-family` everywhere
- Same `font-size` everywhere
- Same `letter-spacing` (default: 0)
- No proportional fonts
- No text transformations

**Testing**:
- Verify alignment with long strings (100+ chars)
- Test with different zoom levels
- Test on different browsers

---

### 4. Event Flow & State Transitions

**Current Flow** (problematic):
```
User types "g"
  → on_user_type("g")
  → classify full buffer
  → update risk_history
  → render
```

**New Flow** (enhanced):
```
User types "g"
  → on_user_type("g", state)
  → Append "g" to buffer
  → Build classifier prompt with full context
  → Get P(RISK) for "g"
  → Store CharClassification with full prompt/response
  → Update EMA
  → Render active section + chart

... user continues typing ...

3-second pause detected
  → check_and_process_buffer(state)
  → Build masker prompt with full context
  → Get entity extractions
  → Create BufferMetadata with all char_data
  → Add to conversation with metadata
  → Generate history HTML with hover tooltips
  → Clear active section
  → Emit masked text to LLM
  → Stream response back

User types during response
  → Mark interruption
  → Stop streaming
  → Save partial response to history
  → Return to input
```

**State Machine**:
```
IDLE → TYPING → PROCESSING → RESPONDING → IDLE
       ↑_____________↓ (interrupt)
```

---

### 5. HTML Generation Strategy

**Flattened Mini-Chart** (for history):
```python
def create_mini_chart(risk_history: list) -> str:
    """Create 2-line flattened chart aligned with text.

    Example:
    User: I need to get my order, my name is [PII/DIRECT].
    Risk: ·  ····  ··  ···  ··  ·····   ··  ····  ··  xxx·x····xx
    EMA:  xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    """
    risk_line = []
    ema_line = []

    for record in risk_history:
        char_idx = record['char_idx']
        p_risk = record['p_risk']
        ema = record['ema']

        # Pad with spaces to align with character position
        while len(risk_line) < char_idx:
            risk_line.append(' ')
            ema_line.append(' ')

        # Risk indicator
        if p_risk >= 0.7:
            risk_line.append('x')  # High risk
        else:
            risk_line.append('·')  # Low risk

        # EMA indicator
        ema_line.append('x')

    risk_html = ''.join(risk_line)
    ema_html = ''.join(ema_line)

    # Color coding
    return f"""
    <div style="color: #5B9BD5;">Risk: {risk_html}</div>
    <div style="color: #90ee90;">EMA:  {ema_html}</div>
    """
```

**Hoverable Text** (with tooltips):
```python
def create_hoverable_text(text: str, char_data: list) -> str:
    """Wrap each character in hoverable span with tooltip."""
    parts = []

    for i, char in enumerate(text):
        if i < len(char_data):
            data = char_data[i]
            tooltip = format_tooltip(data)

            parts.append(
                f'<span class="hoverable" '
                f'data-tooltip="{html_escape(tooltip)}" '
                f'data-idx="{i}">'
                f'{html_escape(char)}'
                f'</span>'
            )
        else:
            parts.append(html_escape(char))

    return ''.join(parts)

def format_tooltip(data: CharClassification) -> str:
    """Format tooltip content as plain text."""
    return f"""
Character: '{data.char}' (index {data.idx})

CLASSIFIER (Stage 1)
Prompt: {format_prompt_compact(data.classifier_prompt)}
Response: P(RISK)={data.risk_score:.3f}

MASKER (Stage 2)
[See full buffer tooltip for masker details]

EMA: {data.ema:.3f}
    """.strip()
```

---

### 6. Performance Optimization

**Potential Bottlenecks**:

1. **Per-character classification** is expensive:
   - Current: Calls `stage1.classify()` for every keystroke
   - Solution: Batch processing? Debouncing? KV cache?

2. **Large HTML generation**:
   - Hoverable spans for 50-char text = 50+ HTML elements
   - Solution: Reasonable, browsers handle this fine

3. **Tooltip data size**:
   - Full prompts can be 500-1000 characters each
   - Solution: Truncate prompts in tooltips, show summary

4. **History accumulation**:
   - Unbounded growth → memory leak
   - Solution: Circular buffer (keep last 20-30 exchanges)

**Optimizations**:

```python
# In PIIClientState:
MAX_HISTORY_SIZE = 30

def add_to_conversation(self, message: dict):
    """Add message and prune old history."""
    with self.lock:
        self.conversation.append(message)

        # Keep only recent history
        if len(self.conversation) > self.MAX_HISTORY_SIZE * 2:  # user+assistant pairs
            self.conversation = self.conversation[-self.MAX_HISTORY_SIZE * 2:]
```

---

### 7. Gradio Layout Structure

**Current Layout** (sidebar):
```python
with gr.Row():
    with gr.Column(scale=3):  # Main
        # Everything
    with gr.Column(scale=1):  # Sidebar
        # Chart
```

**New Layout** (stacked):
```python
with gr.Column():  # Full width vertical stack

    # Top: History (scrollable)
    history_section = gr.HTML(
        label="Conversation History",
        value=create_conversation_history_html([]),
        elem_classes=["history-section"],
        # CSS: max-height: 40vh; overflow-y: auto;
    )

    # Middle: Active I/O
    with gr.Group(elem_classes=["active-section"]):
        active_input = gr.Textbox(
            label="Input",
            placeholder="Type your message...",
            lines=3,
            interactive=True,
        )

        active_response = gr.Textbox(
            label="Assistant Response",
            interactive=False,
            lines=3,
        )

    # Bottom: Chart
    chart_section = gr.HTML(
        label="Risk Metrics",
        value=create_risk_chart([]),
        elem_classes=["chart-section"],
    )
```

**CSS Customization**:
```python
UPDATED_CSS = """
/* Full-width layout */
.gradio-container {
    max-width: 1200px !important;
}

/* History section - scrollable */
.history-section {
    max-height: 40vh;
    overflow-y: auto;
    padding: 12px;
    background-color: #1a1a1a;
    border: 1px solid #333;
    margin-bottom: 20px;
}

/* Active section - prominent */
.active-section {
    background-color: #0d0d0d;
    border: 2px solid #555;
    padding: 16px;
    margin-bottom: 20px;
}

/* Chart section - fixed height */
.chart-section {
    height: 300px;
    background-color: #0d0d0d;
}

/* Hoverable tooltips */
.hoverable {
    position: relative;
    cursor: help;
    border-bottom: 1px dotted #666;
}

.hoverable:hover {
    background-color: #2a2a2a;
}

.hoverable:hover::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 100%;
    left: 0;
    background: #2a2a2a;
    border: 1px solid #555;
    padding: 12px;
    white-space: pre-wrap;
    z-index: 1000;
    max-width: 500px;
    font-size: 12px;
    line-height: 1.4;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}
"""
```

---

## Implementation Phases

### Phase 1: Data Layer (2-3 hours)

**Files to modify**:
- `src/ccpp/gui/state.py`
- `src/ccpp/infer/stage1_router.py`
- `src/ccpp/infer/stage2_redactor.py`

**Tasks**:
1. Create `CharClassification` and `BufferMetadata` dataclasses in `types.py`
2. Update `PIIClientState`:
   - Add `current_char_data: list[CharClassification]`
   - Add `current_buffer_data: Optional[BufferMetadata]`
   - Add circular buffer logic for conversation
3. Update `on_user_type()`:
   - Store full classifier prompt
   - Store classifier response (not just score)
   - Build CharClassification object
4. Update `check_and_process_buffer()`:
   - Store full masker prompt
   - Store masker response
   - Build BufferMetadata
   - Attach to conversation message

### Phase 2: Presentation Layer (2-3 hours)

**Files to modify**:
- `src/ccpp/gui/components.py`
- `src/ccpp/gui/app.py`

**Tasks**:
1. Create `create_hoverable_text()` function
2. Create `create_mini_chart()` function
3. Rewrite `create_conversation_history_html()`:
   - Use hoverable text for user messages
   - Include mini-chart under each user message
   - Show assistant responses
   - Maintain visual hierarchy
4. Update `create_risk_chart()` for bottom section
5. Redesign `create_gui()`:
   - Remove sidebar
   - Create three stacked sections
   - Update event handlers
   - Add new CSS

### Phase 3: Interaction Flow (1 hour)

**Files to modify**:
- `src/ccpp/gui/app.py`

**Tasks**:
1. Update event handlers:
   - `user_input.change` → update active section + chart
   - `timer.tick` → check for stream break, update history
   - `clear_btn.click` → reset all sections
2. Implement interruption logic:
   - Detect typing during response
   - Save partial response
   - Reset to input

### Phase 4: Testing & Refinement (1 hour)

**Tasks**:
1. Test with real PII examples
2. Verify hover tooltips work
3. Verify monospace alignment
4. Test interruption flow
5. Test with long conversations (30+ exchanges)
6. Polish colors and spacing
7. Document any issues

---

## Risk Mitigation

### Risk 1: CSS Tooltips Don't Work in Gradio
**Mitigation**: Test early with simple example. If blocked, fall back to JavaScript or Gradio tooltip API.

### Risk 2: Monospace Alignment Fails
**Mitigation**: Test with various string lengths. Add debugging markers. Consider using `<pre>` tags.

### Risk 3: Performance with Large Prompts
**Mitigation**: Truncate tooltips to 500 chars. Link to "full details" if needed.

### Risk 4: Gradio Updates Break Layout
**Mitigation**: Pin Gradio version in pyproject.toml. Test layout changes carefully.

---

## Success Metrics

**Must Have**:
- ✅ Three distinct vertical sections visible
- ✅ History shows user → mini chart → assistant pattern
- ✅ Hover shows *something* (even if simplified)
- ✅ Chart aligns with text (within 2-3 chars tolerance)
- ✅ No duplicate information displays
- ✅ Clear after stream break

**Nice to Have**:
- ✅ Perfect character alignment
- ✅ Full classifier/masker prompts in tooltips
- ✅ Smooth visual transitions
- ✅ Responsive to window resizing

**Out of Scope** (for now):
- Unmasking capability
- Tooltip content editing
- Export/save conversation
- Performance optimization beyond circular buffer

---

## Next Steps

1. **Get user approval** on this plan
2. **Phase 1**: Implement data layer changes
3. **Quick validation**: Test that metadata is being captured
4. **Phase 2**: Implement presentation layer
5. **Phase 3**: Wire up interaction flow
6. **Phase 4**: Test and refine
7. **Demo**: Show user the result

**Estimated Total Time**: 6-8 hours of focused work

**Questions for User**:
1. Is CSS-only tooltip approach acceptable, or do you need rich HTML tooltips?
2. Should we truncate tooltip prompts to keep them readable?
3. How many exchanges should we keep in history before pruning?
4. Any other specific requirements for the hover tooltip content?
