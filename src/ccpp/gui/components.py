"""UI components for GUI client (clean, professional with good color use)."""

from typing import List, Optional
import html as html_lib


def create_conversation_history_html(conversation: list) -> str:
    """Create HTML showing conversation history with visual hierarchy and hover tooltips.

    Args:
        conversation: List of message dicts with role, content, and optional metadata

    Returns:
        HTML string with grayed-out conversation history, hover tooltips, and mini-charts
    """
    if not conversation:
        return '''<div style="
            font-family: 'Courier New', monospace;
            font-size: 13px;
            padding: 12px;
            color: #666;
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 3px;
            min-height: 150px;
            max-height: 40vh;
            overflow-y: auto;">
            Conversation history will appear here...
        </div>'''

    lines = []
    lines.append('''<div style="
        font-family: 'Courier New', monospace;
        font-size: 13px;
        padding: 12px;
        color: #888;
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 3px;
        line-height: 1.6;
        max-height: 40vh;
        overflow-y: auto;">''')

    lines.append('<div style="color: #666; margin-bottom: 8px;">History</div>')

    for msg in conversation:
        role = msg['role']
        content = msg['content']
        metadata = msg.get('metadata', {})

        if role == "user":
            # User messages with hoverable text and mini-chart
            lines.append(f'<div style="margin: 12px 0; padding: 8px; background-color: #0d0d0d; border-left: 2px solid #7B9FB5;">')
            lines.append(f'  <div style="color: #999; font-size: 11px; margin-bottom: 4px;">User:</div>')

            # Render hoverable text if metadata available
            if metadata and metadata.get('char_data'):
                char_data = metadata['char_data']
                hoverable_html = create_hoverable_text(content, char_data, metadata)
                lines.append(f'  <div style="color: #7B9FB5;">{hoverable_html}</div>')
            else:
                lines.append(f'  <div style="color: #7B9FB5;">{_escape_html(content)}</div>')

            # Add mini-chart summary if available
            if metadata and metadata.get('risk_history'):
                was_masked = metadata.get('was_masked', False)
                # Count entities from masker_response if available
                masker_response = metadata.get('masker_response', {})
                entities = masker_response.get('entities', []) if masker_response else []
                entities_count = len(entities) if entities else (1 if was_masked else 0)
                mini_chart = create_mini_chart(metadata['risk_history'], was_masked=was_masked, entities_count=entities_count)
                lines.append(f'  {mini_chart}')

            # Add collapsible details section for full debug info
            if metadata:
                details_html = _create_details_section(metadata)
                lines.append(f'  {details_html}')

            lines.append('</div>')
        else:
            # Assistant messages in muted gray
            lines.append(f'<div style="margin: 8px 0 12px 0; padding: 8px; background-color: #0d0d0d; border-left: 2px solid #666;">')
            lines.append(f'  <div style="color: #888; font-size: 11px; margin-bottom: 4px;">Assistant:</div>')
            lines.append(f'  <div style="color: #999;">{_escape_html(content)}</div>')
            lines.append('</div>')

    lines.append('</div>')
    return ''.join(lines)


def create_risk_html(text: str, risk_history: list, threshold: float = 0.7) -> str:
    """Create HTML with risk indicators under text.

    Args:
        text: User input text
        risk_history: List of dicts with keys: char_idx, p_risk, ema, any_risk
        threshold: Risk threshold for highlighting (default: 0.7)

    Returns:
        Professional HTML with colored risk indicators
    """
    if not text:
        return '''<div style="
            font-family: 'Courier New', monospace;
            font-size: 14px;
            padding: 12px;
            color: #666;
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 3px;">
            Type to see risk indicators...
        </div>'''

    # Find characters with high risk
    high_risk_chars = set()
    for record in risk_history:
        if record['p_risk'] >= threshold:
            high_risk_chars.add(record['char_idx'])

    # Build HTML
    html_parts = ['''<div style="
        font-family: 'Courier New', monospace;
        font-size: 14px;
        padding: 12px;
        line-height: 1.6;
        color: #eee;
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 3px;">''']

    for i, char in enumerate(text):
        if i in high_risk_chars:
            # Red highlight for high-risk characters
            html_parts.append(
                f'<span style="color: #ff6b6b; background-color: #331a1a; '
                f'border-bottom: 1px solid #ff6b6b; padding: 0 1px;">{_escape_html(char)}</span>'
            )
        else:
            html_parts.append(_escape_html(char))

    html_parts.append('</div>')
    return ''.join(html_parts)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace(' ', '&nbsp;')
        .replace('\n', '<br>')
    )


def _create_details_section(metadata: dict) -> str:
    """Create collapsible HTML details section for debug info.

    Uses HTML <details> element for native expand/collapse without JS.

    Args:
        metadata: BufferMetadata dict with char_data, masker_response, etc.

    Returns:
        HTML string with collapsible details
    """
    lines = []

    lines.append('''<details style="margin-top: 6px; font-size: 11px; color: #888;">
  <summary style="cursor: pointer; color: #666; user-select: none;">Show classifier details</summary>
  <div style="margin-top: 8px; padding: 8px; background: #0a0a0a; border: 1px solid #333; border-radius: 2px; max-height: 70vh; overflow-y: auto;">''')

    # Original vs Masked text
    original = metadata.get('original_text', '')
    masked = metadata.get('masked_text', '')

    if original:
        lines.append(f'<div style="margin-bottom: 8px;"><span style="color: #888;">Original:</span> <span style="color: #7B9FB5;">{html_lib.escape(original)}</span></div>')

    if masked and masked != original:
        lines.append(f'<div style="margin-bottom: 8px;"><span style="color: #888;">Masked:</span> <span style="color: #90ee90;">{html_lib.escape(masked)}</span></div>')

    # Stage 1 classifier info (sample from highest-risk char, not first)
    char_data = metadata.get('char_data', [])
    if char_data:
        # Find the highest-risk character for a representative sample
        def get_risk(c):
            if isinstance(c, dict):
                return c.get('risk_score', 0)
            return getattr(c, 'risk_score', 0)

        max_risk_char = max(char_data, key=get_risk)
        sample = max_risk_char if isinstance(max_risk_char, dict) else max_risk_char.__dict__ if hasattr(max_risk_char, '__dict__') else {}

        lines.append('<div style="margin-top: 8px; border-top: 1px solid #333; padding-top: 8px;">')
        lines.append('<div style="color: #5B9BD5; font-weight: bold; margin-bottom: 4px;">Stage 1: Router (per-token)</div>')

        # Show which character had highest risk
        char_info = sample.get('char', '?') if isinstance(sample, dict) else getattr(sample, 'char', '?')
        char_idx = sample.get('idx', 0) if isinstance(sample, dict) else getattr(sample, 'idx', 0)
        char_risk = get_risk(sample)
        lines.append(f'<div style="color: #888; margin-bottom: 4px;">Highest-risk char: <span style="color: #ff6b6b;">"{html_lib.escape(str(char_info))}"</span> (index {char_idx}, P(RISK)={char_risk:.3f})</div>')

        # Show raw classifier prompt (full, not truncated)
        classifier_prompt = sample.get('classifier_prompt', [])
        if classifier_prompt:
            lines.append('<div style="color: #888; margin-bottom: 4px;">Full prompt sent to classifier:</div>')
            lines.append('<pre style="background: #111; padding: 12px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; font-size: 11px; max-height: 400px; overflow-y: auto; border: 1px solid #333;">')
            for i, msg in enumerate(classifier_prompt):
                role = msg.get('role', 'unknown').upper()
                content = str(msg.get('content', ''))
                escaped_content = html_lib.escape(content)
                # Color-code by role
                if role == 'SYSTEM':
                    role_color = '#FFA500'  # Orange for system
                elif role == 'USER':
                    role_color = '#5B9BD5'  # Blue for user
                else:
                    role_color = '#90ee90'  # Green for assistant
                lines.append(f'<span style="color: {role_color}; font-weight: bold;">═══ {role} ═══</span>\n{escaped_content}\n\n')
            lines.append('</pre>')

        # Show response
        classifier_response = sample.get('classifier_response', {})
        if classifier_response:
            p_risk = classifier_response.get('p_risk', 0)
            p_safe = classifier_response.get('p_safe', 0)
            lines.append(f'<div style="margin-top: 4px;"><span style="color: #888;">Response:</span> P(RISK)={p_risk:.3f}, P(SAFE)={p_safe:.3f}</div>')

        lines.append('</div>')

    # Stage 2 masker info
    masker_response = metadata.get('masker_response')
    if masker_response:
        lines.append('<div style="margin-top: 8px; border-top: 1px solid #333; padding-top: 8px;">')
        lines.append('<div style="color: #ff6b6b; font-weight: bold; margin-bottom: 4px;">Stage 2: Redactor (buffer-level)</div>')

        raw_output = masker_response.get('raw_output', '')
        if raw_output:
            lines.append(f'<div><span style="color: #888;">Output:</span> <span style="color: #ff6b6b;">{html_lib.escape(raw_output)}</span></div>')

        entities = masker_response.get('entities', [])
        if entities:
            lines.append(f'<div><span style="color: #888;">Entities:</span> {len(entities)} detected</div>')

        lines.append('</div>')
    elif metadata.get('was_masked'):
        lines.append('<div style="margin-top: 8px; border-top: 1px solid #333; padding-top: 8px;">')
        lines.append('<div style="color: #ff6b6b; font-weight: bold; margin-bottom: 4px;">Stage 2: Redactor</div>')
        lines.append('<div style="color: #888;">Masking applied</div>')
        lines.append('</div>')

    lines.append('  </div>')
    lines.append('</details>')

    return '\n'.join(lines)


def create_risk_chart(
    risk_history: list,
    t_high: float = 0.6,
    t_low: float = 0.3,
    height: int = 12,
) -> str:
    """Create color-coded ASCII chart showing RISK and EMA (dynamic width based on text length).

    Args:
        risk_history: List of dicts with keys: char_idx, p_risk, ema, any_risk
        t_high: High threshold
        t_low: Low threshold
        height: Chart height in characters (width is auto-calculated from text length)

    Returns:
        HTML string with color-coded ASCII chart
    """
    if not risk_history:
        return '''<div style="
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 12px;
            color: #666;
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 3px;
            white-space: pre;
            line-height: 1.3;
            width: 100%;
            overflow-x: auto;">
RISK and EMA



                Start typing to see metrics...




</div>'''

    # Calculate width from text length (each char gets one column, plus axis space)
    max_idx = max(r["char_idx"] for r in risk_history)
    width = max_idx + 10  # Add padding for axis and labels

    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"[create_risk_chart] Rendering chart: width={width}, height={height}, num_points={len(risk_history)}")


    # Build chart
    chart_lines = _render_color_chart(
        risk_history,
        t_high,
        t_low,
        width,
        height,
    )

    return f'''<div style="
        font-family: 'Courier New', monospace;
        font-size: 12px;
        padding: 12px;
        color: #ccc;
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 3px;
        white-space: pre;
        line-height: 1.3;
        width: 100%;
        overflow-x: auto;">{''.join(chart_lines)}</div>'''


def _render_color_chart(
    risk_history: list,
    t_high: float,
    t_low: float,
    width: int,
    height: int,
) -> List[str]:
    """Render color-coded ASCII chart.

    Returns:
        List of HTML-formatted lines
    """
    # Extract data
    p_risks = [r['p_risk'] for r in risk_history]
    emas = [r['ema'] for r in risk_history]
    char_indices = [r['char_idx'] for r in risk_history]

    # Create canvas - track what type of data is at each position
    canvas = [[None for _ in range(width)] for _ in range(height)]

    # Draw axes
    for y in range(height):
        canvas[y][0] = ('axis', '│')

    for x in range(width):
        canvas[height - 1][x] = ('axis', '─')

    canvas[height - 1][0] = ('axis', '└')

    # Draw threshold lines
    t_high_y = _value_to_y(t_high, height)
    t_low_y = _value_to_y(t_low, height)

    for x in range(1, width):
        if t_high_y < height - 1 and canvas[t_high_y][x] is None:
            canvas[t_high_y][x] = ('threshold_high', '─')
        if t_low_y < height - 1 and canvas[t_low_y][x] is None:
            canvas[t_low_y][x] = ('threshold_low', '─')

    # Normalize indices
    max_char = max(char_indices)
    min_char = min(char_indices)
    char_range = max(max_char - min_char, 1)

    # Plot P(RISK) with dots
    for char_idx, p_risk in zip(char_indices, p_risks):
        x = _char_to_x(char_idx, min_char, char_range, width)
        y = _value_to_y(p_risk, height)
        if 0 < x < width and 0 <= y < height - 1:
            canvas[y][x] = ('risk', '·')

    # Plot EMA with x's (will override dots where they overlap)
    current_ema = emas[-1]
    ema_escalated = current_ema >= t_high

    for char_idx, ema in zip(char_indices, emas):
        x = _char_to_x(char_idx, min_char, char_range, width)
        y = _value_to_y(ema, height)
        if 0 < x < width and 0 <= y < height - 1:
            canvas[y][x] = ('ema_high' if ema >= t_high else 'ema_low', 'x')

    # Convert to HTML
    lines = []
    lines.append('<span style="color: #aaa;">RISK and EMA</span>\n\n')

    for y, row in enumerate(canvas):
        line_parts = []

        for x, cell in enumerate(row):
            if cell is None:
                line_parts.append(' ')
            else:
                cell_type, char = cell

                if cell_type == 'axis':
                    line_parts.append(f'<span style="color: #444;">{char}</span>')
                elif cell_type == 'threshold_high':
                    line_parts.append(f'<span style="color: #FFA500;">{char}</span>')
                elif cell_type == 'threshold_low':
                    line_parts.append(f'<span style="color: #666;">{char}</span>')
                elif cell_type == 'risk':
                    line_parts.append(f'<span style="color: #5B9BD5;">·</span>')
                elif cell_type == 'ema_high':
                    line_parts.append(f'<span style="color: #ff6b6b;">x</span>')
                elif cell_type == 'ema_low':
                    line_parts.append(f'<span style="color: #90ee90;">x</span>')

        # Add labels on right
        if y == t_high_y:
            line_parts.append(f'<span style="color: #FFA500;"> EMA High</span>')
        elif y == t_low_y:
            line_parts.append(f'<span style="color: #666;"> EMA Low</span>')

        lines.append(''.join(line_parts) + '\n')

    # Add current values and legend
    current_risk = p_risks[-1]
    current_ema = emas[-1]

    lines.append('\n')
    lines.append(f'<span style="color: #5B9BD5;">·</span> RISK={current_risk:.3f}  ')

    ema_color = '#ff6b6b' if current_ema >= t_high else '#90ee90'
    lines.append(f'<span style="color: {ema_color};">x</span> EMA={current_ema:.3f}\n')

    return lines


def _value_to_y(value: float, height: int) -> int:
    """Convert risk value (0-1) to y coordinate."""
    y = int((1.0 - value) * (height - 2))
    return max(0, min(height - 2, y))


def _char_to_x(char_idx: int, min_char: int, char_range: int, width: int) -> int:
    """Convert character index to x coordinate.

    Use 1:1 mapping so each character gets its own column.
    """
    x = char_idx - min_char + 1  # +1 for axis
    return max(1, min(width - 1, x))


def create_hoverable_text(text: str, char_data: list, buffer_metadata: Optional[dict] = None) -> str:
    """Create HTML text with clickable words that expand to show classifier data.

    Uses click-to-expand (not hover) for better UX. Each word can be clicked
    to show its classification details in a scrollable popup.

    Args:
        text: The text to render (masked version)
        char_data: List of CharClassification dicts (from original text)
        buffer_metadata: Optional buffer metadata for masker info

    Returns:
        HTML string with clickable text
    """
    import re

    # Highlight masked placeholders in the text
    escaped_text = _escape_html(text)
    # Make [PII/...] placeholders red and bold
    escaped_text = re.sub(
        r'\[([A-Z/_]+)\]',
        r'<span style="color: #ff6b6b; font-weight: bold;">[\1]</span>',
        escaped_text
    )

    return escaped_text


def _format_tooltip(char_info: dict, buffer_metadata: Optional[dict] = None) -> str:
    """Format tooltip content as plain text.

    Args:
        char_info: CharClassification dict
        buffer_metadata: Optional buffer metadata

    Returns:
        Plain text tooltip content
    """
    lines = []

    # Character info
    lines.append(f"Character: '{char_info['char']}' (index {char_info['idx']})")
    lines.append("")

    # Stage 1 Classifier
    lines.append("STAGE 1 CLASSIFIER")
    lines.append("-" * 40)

    # Show simplified prompt (full prompts can be very long)
    classifier_prompt = char_info.get('classifier_prompt', [])
    if classifier_prompt:
        lines.append("Prompt (simplified):")
        for msg in classifier_prompt[-2:]:  # Show last 2 messages
            role = msg.get('role', '').upper()
            content = msg.get('content', '')[:100]  # Truncate long content
            if len(msg.get('content', '')) > 100:
                content += "..."
            lines.append(f"  {role}: {content}")
    else:
        lines.append("Prompt: [Mock mode - no actual prompt]")

    # Show response
    classifier_response = char_info.get('classifier_response', {})
    p_risk = classifier_response.get('p_risk', 0.0)
    p_safe = classifier_response.get('p_safe', 0.0)
    lines.append("")
    lines.append(f"Response: P(RISK)={p_risk:.3f}, P(SAFE)={p_safe:.3f}")
    lines.append(f"EMA after this char: {char_info['ema']:.3f}")

    # Stage 2 Masker (if available)
    if buffer_metadata:
        lines.append("")
        lines.append("STAGE 2 MASKER (Buffer-level)")
        lines.append("-" * 40)

        masker_response = buffer_metadata.get('masker_response')
        if masker_response:
            lines.append(f"Response: {masker_response.get('raw_output', 'N/A')}")
        else:
            lines.append("Not triggered (low risk)")

        # Show original text
        original = buffer_metadata.get('original_text', '')
        lines.append("")
        lines.append(f"Original buffer: {original}")

    return "\n".join(lines)


def create_mini_chart(risk_history: list, was_masked: bool = False, entities_count: int = 0) -> str:
    """Create compact summary line for conversation history.

    Args:
        risk_history: List of risk_history dicts
        was_masked: Whether masking was applied
        entities_count: Number of entities masked

    Returns:
        HTML string with summary metrics
    """
    if not risk_history:
        return ""

    # Calculate summary stats
    p_risks = [r['p_risk'] for r in risk_history]
    emas = [r['ema'] for r in risk_history]

    peak_risk = max(p_risks)
    final_ema = emas[-1]
    high_risk_count = sum(1 for r in p_risks if r >= 0.7)

    # Determine status color based on outcome
    if was_masked:
        status_color = "#ff6b6b"  # Red for masked
        status_text = f"MASKED ({entities_count} entities)"
    elif peak_risk >= 0.7:
        status_color = "#FFA500"  # Orange for high risk but not masked
        status_text = "HIGH RISK"
    else:
        status_color = "#90ee90"  # Green for safe
        status_text = "SAFE"

    # Determine EMA color
    ema_color = "#ff6b6b" if final_ema >= 0.6 else ("#FFA500" if final_ema >= 0.3 else "#90ee90")

    return f'''<div style="font-family: 'Courier New', monospace; font-size: 11px; line-height: 1.4; margin-top: 4px; padding: 4px 6px; background: #0a0a0a; border-radius: 2px;">
<span style="color: {status_color}; font-weight: bold;">{status_text}</span>
<span style="color: #666;"> | </span>
<span style="color: #888;">Peak: </span><span style="color: #5B9BD5;">{peak_risk:.2f}</span>
<span style="color: #666;"> | </span>
<span style="color: #888;">EMA: </span><span style="color: {ema_color};">{final_ema:.2f}</span>
<span style="color: #666;"> | </span>
<span style="color: #888;">High-risk chars: </span><span style="color: {'#ff6b6b' if high_risk_count > 0 else '#666'};">{high_risk_count}</span>
</div>'''


def format_status(
    is_processing: bool = False,
    chars_processed: int = 0,
    chars_masked: int = 0,
    error: str = "",
) -> str:
    """Format status message with appropriate colors.

    Args:
        is_processing: Whether currently processing
        chars_processed: Number of original characters
        chars_masked: Number of characters in masked version
        error: Error message if any

    Returns:
        Colored HTML status string
    """
    if error:
        return f'''<div style="
            font-family: 'Courier New', monospace;
            padding: 8px;
            color: #ff6b6b;
            background-color: #1a1a1a;
            border: 1px solid #ff6b6b;
            border-radius: 3px;
            font-size: 13px;">
            Error: {error}
        </div>'''

    if is_processing:
        return '''<div style="
            font-family: 'Courier New', monospace;
            padding: 8px;
            color: #FFD700;
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 3px;
            font-size: 13px;">
            Processing buffer and waiting for LLM response...
        </div>'''

    if chars_processed > 0:
        return f'''<div style="
            font-family: 'Courier New', monospace;
            padding: 8px;
            color: #90ee90;
            background-color: #1a1a1a;
            border: 1px solid #90ee90;
            border-radius: 3px;
            font-size: 13px;">
            Processed: {chars_processed} chars → {chars_masked} chars masked
        </div>'''

    return '''<div style="
        font-family: 'Courier New', monospace;
        padding: 8px;
        color: #888;
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 3px;
        font-size: 13px;">
        Ready - start typing (pause 3s to send)
    </div>'''
