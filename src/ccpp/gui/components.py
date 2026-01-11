"""UI components for GUI client (terminal-style charts, HTML formatting, etc.)."""

import math
from typing import List, Tuple


def create_risk_html(text: str, risk_history: list, threshold: float = 0.7) -> str:
    """Create terminal-style HTML with risk indicators under text.

    Highlights characters that triggered high risk scores with terminal colors.

    Args:
        text: User input text
        risk_history: List of dicts with keys: char_idx, p_risk, ema, any_risk
        threshold: Risk threshold for highlighting (default: 0.7)

    Returns:
        Terminal-styled HTML string with risk indicators
    """
    if not text:
        return '''<div style="
            font-family: 'Courier New', monospace;
            font-size: 14px;
            padding: 12px;
            color: #00ff00;
            background-color: #0a0a0a;
            border: 1px solid #333;
            border-radius: 4px;">
            <span style="color: #666;">▸ Type to see risk indicators...</span>
        </div>'''

    if not risk_history:
        return f'''<div style="
            font-family: 'Courier New', monospace;
            font-size: 14px;
            padding: 12px;
            color: #00ff00;
            background-color: #0a0a0a;
            border: 1px solid #333;
            border-radius: 4px;">
            {_escape_html(text)}
        </div>'''

    # Find characters with high risk
    high_risk_chars = set()
    for record in risk_history:
        if record['p_risk'] >= threshold:
            high_risk_chars.add(record['char_idx'])

    # Build terminal-style HTML with highlighting
    html_parts = ['''<div style="
        font-family: 'Courier New', monospace;
        font-size: 14px;
        padding: 12px;
        line-height: 1.8;
        color: #00ff00;
        background-color: #0a0a0a;
        border: 1px solid #333;
        border-radius: 4px;">''']

    for i, char in enumerate(text):
        if i in high_risk_chars:
            # Highlight risky characters with red (terminal style)
            html_parts.append(
                f'<span style="color: #ff0000; background-color: #330000; '
                f'border-bottom: 2px solid #ff0000; padding: 1px; '
                f'font-weight: bold;">{_escape_html(char)}</span>'
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


def create_risk_chart(
    risk_history: list,
    t_high: float = 0.6,
    t_low: float = 0.3,
    width: int = 80,
    height: int = 20,
) -> str:
    """Create terminal-style ASCII chart showing P(RISK) and EMA over time.

    Args:
        risk_history: List of dicts with keys: char_idx, p_risk, ema, any_risk
        t_high: High threshold for escalation (default: 0.6)
        t_low: Low threshold for de-escalation (default: 0.3)
        width: Chart width in characters (default: 80)
        height: Chart height in characters (default: 20)

    Returns:
        HTML string containing terminal-style ASCII chart

    Example:
        >>> history = [{'char_idx': 0, 'p_risk': 0.5, 'ema': 0.4, 'any_risk': False}]
        >>> html = create_risk_chart(history)
    """
    # Create empty chart if no data
    if not risk_history:
        return '''<div style="
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 12px;
            color: #00ff00;
            background-color: #0a0a0a;
            border: 1px solid #333;
            border-radius: 4px;
            white-space: pre;">
┌─ RISK METRICS ─────────────────────────────────────────────────────┐
│                                                                    │
│                   <span style="color: #666;">Start typing to see metrics...</span>                   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
</div>'''

    # Determine current EMA color
    current_ema = risk_history[-1]['ema']
    ema_color = '#ff0000' if current_ema >= t_high else '#00ff00'

    # Build ASCII chart
    chart_lines = _render_ascii_chart(
        risk_history,
        t_high,
        t_low,
        width,
        height,
        ema_color,
    )

    # Wrap in terminal-style HTML
    return f'''<div style="
        font-family: 'Courier New', monospace;
        font-size: 12px;
        padding: 12px;
        color: #00ff00;
        background-color: #0a0a0a;
        border: 1px solid #333;
        border-radius: 4px;
        white-space: pre;
        line-height: 1.2;">{''.join(chart_lines)}</div>'''


def _render_ascii_chart(
    risk_history: list,
    t_high: float,
    t_low: float,
    width: int,
    height: int,
    ema_color: str,
) -> List[str]:
    """Render ASCII chart with P(RISK) and EMA lines.

    Returns:
        List of HTML-formatted lines
    """
    # Extract data
    p_risks = [r['p_risk'] for r in risk_history]
    emas = [r['ema'] for r in risk_history]
    char_indices = [r['char_idx'] for r in risk_history]

    # Create canvas
    canvas = [[' ' for _ in range(width)] for _ in range(height)]

    # Draw axes
    for y in range(height):
        canvas[y][0] = '│'

    for x in range(width):
        canvas[height - 1][x] = '─'

    canvas[height - 1][0] = '└'

    # Draw threshold lines
    t_high_y = _value_to_y(t_high, height)
    t_low_y = _value_to_y(t_low, height)

    for x in range(1, width):
        if t_high_y < height - 1:
            canvas[t_high_y][x] = '┈'  # Dashed line for T_high
        if t_low_y < height - 1:
            canvas[t_low_y][x] = '·'  # Dotted line for T_low

    # Normalize char indices to fit width
    max_char = max(char_indices)
    min_char = min(char_indices)
    char_range = max(max_char - min_char, 1)

    # Plot P(RISK) line (blue)
    for i, (char_idx, p_risk) in enumerate(zip(char_indices, p_risks)):
        x = _char_to_x(char_idx, min_char, char_range, width)
        y = _value_to_y(p_risk, height)
        if 0 < x < width and 0 <= y < height - 1:
            canvas[y][x] = '●'  # P(RISK) marker

    # Plot EMA line (green/red depending on threshold)
    for i, (char_idx, ema) in enumerate(zip(char_indices, emas)):
        x = _char_to_x(char_idx, min_char, char_range, width)
        y = _value_to_y(ema, height)
        if 0 < x < width and 0 <= y < height - 1:
            canvas[y][x] = '█'  # EMA marker (solid block)

    # Convert canvas to HTML lines with colors
    lines = ['┌─ RISK METRICS ─────────────────────────────────────────────────────┐\n']

    for y, row in enumerate(canvas):
        line_parts = ['│']

        for x, char in enumerate(row):
            if char == '●':  # P(RISK) marker
                line_parts.append(f'<span style="color: #00aaff;">●</span>')
            elif char == '█':  # EMA marker
                line_parts.append(f'<span style="color: {ema_color};">█</span>')
            elif char == '┈':  # T_high line
                line_parts.append(f'<span style="color: #ff9800;">┈</span>')
            elif char == '·':  # T_low line
                line_parts.append(f'<span style="color: #666;">·</span>')
            elif char == '│' or char == '─' or char == '└':
                line_parts.append(f'<span style="color: #444;">{char}</span>')
            else:
                line_parts.append(' ')

        line_parts.append('<span style="color: #444;">│</span>\n')
        lines.append(''.join(line_parts))

    # Add legend
    lines.append('└────────────────────────────────────────────────────────────────────┘\n')
    lines.append(f'  <span style="color: #00aaff;">●</span> P(RISK)  ')
    lines.append(f'<span style="color: {ema_color};">█</span> EMA  ')
    lines.append(f'<span style="color: #ff9800;">┈</span> T_high={t_high:.2f}  ')
    lines.append(f'<span style="color: #666;">·</span> T_low={t_low:.2f}\n')

    # Add current values
    current_p_risk = p_risks[-1]
    current_ema = emas[-1]
    lines.append(f'  Current: P(RISK)=<span style="color: #00aaff;">{current_p_risk:.3f}</span>  ')
    lines.append(f'EMA=<span style="color: {ema_color};">{current_ema:.3f}</span>\n')

    return lines


def _value_to_y(value: float, height: int) -> int:
    """Convert risk value (0-1) to y coordinate."""
    # Invert because y=0 is top
    y = int((1.0 - value) * (height - 2))
    return max(0, min(height - 2, y))


def _char_to_x(char_idx: int, min_char: int, char_range: int, width: int) -> int:
    """Convert character index to x coordinate."""
    normalized = (char_idx - min_char) / char_range
    x = int(normalized * (width - 2)) + 1
    return max(1, min(width - 1, x))


def format_status(
    is_processing: bool = False,
    chars_processed: int = 0,
    chars_masked: int = 0,
    error: str = "",
) -> str:
    """Format terminal-style status message for display.

    Args:
        is_processing: Whether currently processing
        chars_processed: Number of original characters
        chars_masked: Number of characters in masked version
        error: Error message if any

    Returns:
        Terminal-styled HTML status string
    """
    if error:
        return f'''<div style="
            font-family: 'Courier New', monospace;
            padding: 8px;
            color: #ff0000;
            background-color: #0a0a0a;
            border: 1px solid #ff0000;
            border-radius: 4px;">
            <span style="color: #ff0000;">✗ ERROR:</span> {error}
        </div>'''

    if is_processing:
        return '''<div style="
            font-family: 'Courier New', monospace;
            padding: 8px;
            color: #ffaa00;
            background-color: #0a0a0a;
            border: 1px solid #333;
            border-radius: 4px;">
            <span style="color: #ffaa00;">⧗</span> Processing buffer and waiting for LLM response...
        </div>'''

    if chars_processed > 0:
        return f'''<div style="
            font-family: 'Courier New', monospace;
            padding: 8px;
            color: #00ff00;
            background-color: #0a0a0a;
            border: 1px solid #00ff00;
            border-radius: 4px;">
            <span style="color: #00ff00;">✓</span> Processed! Original: {chars_processed} chars, Masked: {chars_masked} chars
        </div>'''

    return '''<div style="
        font-family: 'Courier New', monospace;
        padding: 8px;
        color: #00aaff;
        background-color: #0a0a0a;
        border: 1px solid #333;
        border-radius: 4px;">
        <span style="color: #00aaff;">▸</span> Ready - start typing! (pause for 3 seconds to send)
    </div>'''
