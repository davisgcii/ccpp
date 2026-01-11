"""UI components for GUI client (charts, HTML formatting, etc.)."""

import plotly.graph_objects as go
import pandas as pd


def create_risk_html(text: str, risk_history: list, threshold: float = 0.7) -> str:
    """Create HTML with risk indicators under text.

    Highlights characters that triggered high risk scores with red background
    and underline.

    Args:
        text: User input text
        risk_history: List of dicts with keys: char_idx, p_risk, ema, any_risk
        threshold: Risk threshold for highlighting (default: 0.7)

    Returns:
        HTML string with risk indicators

    Example:
        >>> create_risk_html("test@email.com", [{'char_idx': 5, 'p_risk': 0.9, ...}])
        '<div style="...">test<span style="background-color: #ffcccc;">@</span>...</div>'
    """
    if not text:
        return '<div style="font-size: 16px; padding: 10px; color: #888;">Type to see risk indicators...</div>'

    if not risk_history:
        return f'<div style="font-size: 16px; padding: 10px;">{text}</div>'

    # Find characters with high risk
    high_risk_chars = set()
    for record in risk_history:
        if record['p_risk'] >= threshold:
            high_risk_chars.add(record['char_idx'])

    # Build HTML with highlighting
    html_parts = [
        '<div style="font-size: 16px; padding: 10px; line-height: 2.0; '
        'font-family: monospace; background-color: #f9f9f9; border-radius: 4px;">'
    ]

    for i, char in enumerate(text):
        if i in high_risk_chars:
            # Highlight risky characters with red background and underline
            html_parts.append(
                f'<span style="background-color: #ffcccc; '
                f'border-bottom: 2px solid #cc0000; padding: 2px; '
                f'font-weight: bold;">{char}</span>'
            )
        else:
            # Escape HTML special characters
            if char == '<':
                html_parts.append('&lt;')
            elif char == '>':
                html_parts.append('&gt;')
            elif char == '&':
                html_parts.append('&amp;')
            else:
                html_parts.append(char)

    html_parts.append('</div>')

    return ''.join(html_parts)


def create_risk_chart(
    risk_history: list,
    t_high: float = 0.6,
    t_low: float = 0.3,
) -> go.Figure:
    """Create Plotly chart showing P(RISK) and EMA over time.

    Args:
        risk_history: List of dicts with keys: char_idx, p_risk, ema, any_risk
        t_high: High threshold for escalation (default: 0.6)
        t_low: Low threshold for de-escalation (default: 0.3)

    Returns:
        Plotly figure object

    Example:
        >>> history = [{'char_idx': 0, 'p_risk': 0.5, 'ema': 0.4, 'any_risk': False}]
        >>> fig = create_risk_chart(history)
    """
    # Create empty chart if no data
    if not risk_history:
        fig = go.Figure()
        fig.update_layout(
            title="Risk Metrics (P(RISK) and EMA)",
            xaxis_title="Character Index",
            yaxis_title="Risk Score",
            yaxis_range=[0, 1],
            height=350,
            template="plotly_white",
        )
        fig.add_annotation(
            text="Start typing to see risk metrics...",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="gray"),
        )
        return fig

    # Convert to DataFrame for easy plotting
    df = pd.DataFrame(risk_history)

    # Determine EMA line color (red if above threshold, green otherwise)
    current_ema = df['ema'].iloc[-1] if len(df) > 0 else 0.0
    ema_color = '#cc0000' if current_ema >= t_high else '#00cc00'

    fig = go.Figure()

    # P(RISK) line (per-character risk)
    fig.add_trace(go.Scatter(
        x=df['char_idx'],
        y=df['p_risk'],
        mode='lines',
        name='P(RISK) per char',
        line=dict(color='#4285f4', width=2),
        hovertemplate='Char %{x}<br>P(RISK): %{y:.3f}<extra></extra>',
    ))

    # EMA line (smoothed risk)
    fig.add_trace(go.Scatter(
        x=df['char_idx'],
        y=df['ema'],
        mode='lines',
        name='EMA (smoothed)',
        line=dict(color=ema_color, width=3),
        hovertemplate='Char %{x}<br>EMA: %{y:.3f}<extra></extra>',
    ))

    # High threshold line
    fig.add_hline(
        y=t_high,
        line_dash="dash",
        line_color="#ff9800",
        line_width=2,
        annotation_text=f"T_high = {t_high}",
        annotation_position="right",
        annotation=dict(font_size=12, font_color="#ff9800"),
    )

    # Low threshold line (optional, for reference)
    fig.add_hline(
        y=t_low,
        line_dash="dot",
        line_color="#999999",
        line_width=1,
        annotation_text=f"T_low = {t_low}",
        annotation_position="right",
        annotation=dict(font_size=10, font_color="#999999"),
    )

    # Layout
    fig.update_layout(
        title={
            'text': "Risk Metrics Over Time",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16, 'weight': 'bold'},
        },
        xaxis_title="Character Index",
        yaxis_title="Risk Score",
        yaxis_range=[0, 1.05],  # Slightly above 1 for better visibility
        height=350,
        showlegend=True,
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="gray",
            borderwidth=1,
        ),
        template="plotly_white",
        hovermode='x unified',
    )

    # Add grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')

    return fig


def format_status(
    is_processing: bool = False,
    chars_processed: int = 0,
    chars_masked: int = 0,
    error: str = "",
) -> str:
    """Format status message for display.

    Args:
        is_processing: Whether currently processing
        chars_processed: Number of original characters
        chars_masked: Number of characters in masked version
        error: Error message if any

    Returns:
        Formatted status string
    """
    if error:
        return f"❌ Error: {error}"

    if is_processing:
        return "⏳ Processing buffer and waiting for LLM response..."

    if chars_processed > 0:
        return (
            f"✅ Processed! Original: {chars_processed} chars, "
            f"Masked: {chars_masked} chars"
        )

    return "💬 Ready - start typing! (pause for 3 seconds to send)"
