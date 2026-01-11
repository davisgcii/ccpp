"""Main Gradio application for PII-masked chat GUI (terminal-style)."""

import time
import gradio as gr

from ccpp.gui.state import PIIClientState
from ccpp.gui.components import create_risk_html, create_risk_chart, format_status
from ccpp.types import ApprovedModel


# Terminal-style CSS
TERMINAL_CSS = """
/* Dark terminal theme */
body {
    background-color: #000000 !important;
}

.gradio-container {
    background-color: #0a0a0a !important;
    font-family: 'Courier New', monospace !important;
}

/* Terminal-style textboxes */
.terminal-input textarea, .terminal-output textarea {
    font-family: 'Courier New', monospace !important;
    background-color: #0a0a0a !important;
    color: #00ff00 !important;
    border: 1px solid #333 !important;
    border-radius: 4px !important;
}

.terminal-input textarea:focus, .terminal-output textarea:focus {
    border-color: #00ff00 !important;
    box-shadow: 0 0 5px #00ff00 !important;
}

/* Labels */
label {
    color: #00ff00 !important;
    font-family: 'Courier New', monospace !important;
    font-weight: bold !important;
}

/* Buttons */
button {
    background-color: #1a1a1a !important;
    color: #00ff00 !important;
    border: 1px solid #333 !important;
    font-family: 'Courier New', monospace !important;
}

button:hover {
    background-color: #2a2a2a !important;
    border-color: #00ff00 !important;
}

/* Markdown */
.markdown {
    color: #00ff00 !important;
}
"""


def on_user_type(text: str, state: PIIClientState):
    """Handle user typing event (fires on every character change).

    Args:
        text: Current text in input box
        state: Application state

    Returns:
        Tuple of (risk_html, risk_chart, status_text)
    """
    with state.lock:
        # If currently processing LLM response, mark for interruption
        if state.is_processing:
            state.should_interrupt = True

        # Update buffer and timing
        state.buffer = text
        state.last_input_time = time.time()

        # Clear risk history if text is empty
        if not text:
            state.risk_history = []
            return (
                create_risk_html("", []),
                create_risk_chart([]),
                format_status(),
            )

        # Process through Stage 1 (per-character classification)
        # In practice, we'd optimize this to only process new characters
        risk_score = state.stage1.classify(state.conversation, text)

        # Update EMA
        ema = state.guard.risk_state.update(risk_score.score)
        any_risk = risk_score.score >= state.guard.risk_threshold_immediate

        # Add to risk history
        state.risk_history.append({
            'char_idx': len(text) - 1,
            'p_risk': risk_score.score,
            'ema': ema,
            'any_risk': any_risk,
        })

        # Generate outputs
        risk_html = create_risk_html(
            text,
            state.risk_history,
            threshold=state.guard.risk_threshold_immediate,
        )
        risk_chart = create_risk_chart(
            state.risk_history,
            t_high=state.guard.risk_threshold_high,
            t_low=state.guard.risk_threshold_low,
        )
        status_text = format_status()

        return risk_html, risk_chart, status_text


def check_and_process_buffer(state: PIIClientState):
    """Check for stream break and process buffer if ready.

    This function is called by a timer every 500ms. It detects stream breaks
    (user paused typing for configured timeout) and processes the buffer through
    the PII masker, then calls the LLM.

    Args:
        state: Application state

    Returns:
        Tuple of (original_text, masked_text, assistant_text, status_text)
    """
    # Check if we should process
    if not state.should_process_buffer():
        return gr.update(), gr.update(), gr.update(), gr.update()

    with state.lock:
        # Mark as processing
        state.is_processing = True
        state.should_interrupt = False

        # Get original text
        original_text = state.buffer

        # Reset guard for clean processing
        state.guard.reset()

        # Process buffer through guard (character by character)
        masked_text = ""
        for char in original_text:
            emit, _ = state.guard.ingest_chunk(char)
            if emit:
                masked_text += emit

        # Force emit remaining buffer
        final_emit, _ = state.guard.force_emit()
        if final_emit:
            masked_text += final_emit

        # Mark buffer as processed
        state.processed_buffer = state.buffer

        # Add user message to conversation
        state.conversation.append({
            "role": "user",
            "content": masked_text,
        })

        # Call LLM (if available)
        assistant_text = ""
        if state.anthropic:
            try:
                # Make synchronous call to Claude
                # Note: True streaming would require more complex Gradio setup
                response = state.anthropic.messages.create(
                    model=ApprovedModel.CLAUDE_HAIKU_4_5.value,
                    max_tokens=1024,
                    messages=state.conversation,
                )

                # Check if interrupted during call
                if state.should_interrupt:
                    # User started typing - don't add response to history
                    assistant_text = "[Response interrupted - user started typing]"
                else:
                    # Complete response
                    assistant_text = response.content[0].text

                    # Add to conversation history
                    state.conversation.append({
                        "role": "assistant",
                        "content": assistant_text,
                    })

            except Exception as e:
                assistant_text = f"[LLM error: {e}]"

        else:
            assistant_text = "[LLM unavailable - no API key configured]"

        # Update status
        status_text = format_status(
            is_processing=False,
            chars_processed=len(original_text),
            chars_masked=len(masked_text),
        )

        # Mark processing complete
        state.is_processing = False

        return original_text, masked_text, assistant_text, status_text


def clear_conversation(state: PIIClientState):
    """Clear all conversation state and reset UI.

    Args:
        state: Application state

    Returns:
        Tuple of all cleared UI elements
    """
    state.reset()

    return (
        "",  # user_input
        create_risk_html("", []),  # risk_indicators
        create_risk_chart([]),  # risk_chart
        format_status(),  # status
        "",  # original_display
        "",  # masked_display
        "",  # assistant_display
    )


def create_gui(state: PIIClientState) -> gr.Blocks:
    """Create Gradio interface for PII-masked chat (terminal-style).

    Args:
        state: Application state instance

    Returns:
        Gradio Blocks interface with terminal aesthetics
    """
    # Create dark theme
    theme = gr.themes.Base(
        primary_hue="green",
        secondary_hue="green",
        neutral_hue="slate",
    ).set(
        body_background_fill="#000000",
        body_background_fill_dark="#000000",
        panel_background_fill="#0a0a0a",
        panel_background_fill_dark="#0a0a0a",
    )

    with gr.Blocks(
        title="[PII-GUARD] Terminal Interface",
        theme=theme,
        css=TERMINAL_CSS,
    ) as demo:
        # Terminal-style header
        gr.HTML('''
        <div style="
            font-family: 'Courier New', monospace;
            padding: 20px;
            background-color: #0a0a0a;
            border: 2px solid #00ff00;
            border-radius: 4px;
            margin-bottom: 20px;">
            <h1 style="color: #00ff00; margin: 0; font-size: 24px;">
                ┌─ PII-GUARD TERMINAL ──────────────────────────────────────┐
            </h1>
            <pre style="color: #00aaff; margin: 10px 0; font-size: 12px;">
├─ Real-time PII detection and masking
├─ Live risk visualization (ASCII charts)
├─ Stream break detection (3s pause)
├─ Automatic masking before LLM submission
└─ Interrupt protection (type to cancel response)
            </pre>
            <p style="color: #ffaa00; margin: 5px 0; font-size: 12px;">
                <span style="color: #ff0000;">⚠</span> CLASSIFIED - Authorized Personnel Only
            </p>
        </div>
        ''')

        with gr.Row():
            # Left column: Input and outputs
            with gr.Column(scale=2):
                # User input area
                user_input = gr.Textbox(
                    label="▸ INPUT STREAM",
                    placeholder="[WAITING FOR INPUT] Type PII to test detection...",
                    lines=3,
                    interactive=True,
                    elem_classes=["terminal-input"],
                )

                # Risk indicators
                risk_indicators = gr.HTML(
                    label="▸ RISK INDICATORS",
                    value=create_risk_html("", []),
                )

                # Status bar
                status = gr.HTML(
                    label="▸ SYSTEM STATUS",
                    value=format_status(),
                )

                # Original vs Masked comparison
                gr.HTML('''<div style="
                    color: #00ff00;
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                    padding: 10px 0;
                    border-top: 1px solid #333;
                    margin-top: 10px;">
                    ┌─ COMPARISON: ORIGINAL vs MASKED ─────────────────────┐
                </div>''')
                with gr.Row():
                    original_display = gr.Textbox(
                        label="▸ ORIGINAL",
                        interactive=False,
                        lines=3,
                        placeholder="[EMPTY] Waiting for stream break...",
                        elem_classes=["terminal-output"],
                    )
                    masked_display = gr.Textbox(
                        label="▸ MASKED (TO LLM)",
                        interactive=False,
                        lines=3,
                        placeholder="[EMPTY] Waiting for stream break...",
                        elem_classes=["terminal-output"],
                    )

                # Assistant response
                assistant_display = gr.Textbox(
                    label="▸ LLM RESPONSE",
                    interactive=False,
                    lines=6,
                    placeholder="[STANDBY] Waiting for LLM response...",
                    elem_classes=["terminal-output"],
                )

                # Control buttons
                with gr.Row():
                    clear_btn = gr.Button("[ CLEAR SESSION ]", variant="secondary")

            # Right column: Risk chart and legend
            with gr.Column(scale=1):
                # ASCII Risk chart
                risk_chart = gr.HTML(
                    label="▸ RISK VISUALIZATION",
                    value=create_risk_chart([]),
                )

                # Terminal-style legend
                gr.HTML('''
                <div style="
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    padding: 12px;
                    color: #00ff00;
                    background-color: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    margin-top: 10px;">
                    <div style="color: #ffaa00; font-weight: bold; margin-bottom: 8px;">
                    ┌─ LEGEND ──────────────────────────┐
                    </div>
                    <div style="color: #00aaff;">● P(RISK)</div>
                    <div style="margin-left: 10px; color: #666;">Per-character risk score</div>
                    <br>
                    <div><span style="color: #00ff00;">█</span><span style="color: #ff0000;">█</span> EMA (smoothed)</div>
                    <div style="margin-left: 10px; color: #666;">Green: safe / Red: escalated</div>
                    <br>
                    <div style="color: #ff9800;">┈ T_high (0.6)</div>
                    <div style="margin-left: 10px; color: #666;">Escalation threshold</div>
                    <br>
                    <div style="color: #666;">· T_low (0.3)</div>
                    <div style="margin-left: 10px; color: #666;">De-escalation threshold</div>
                    <div style="color: #ffaa00; font-weight: bold; margin-top: 8px;">
                    └───────────────────────────────────┘
                    </div>
                </div>
                ''')

                # Terminal-style usage tips
                gr.HTML('''
                <div style="
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    padding: 12px;
                    color: #00ff00;
                    background-color: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    margin-top: 10px;">
                    <div style="color: #ffaa00; font-weight: bold; margin-bottom: 8px;">
                    ┌─ USAGE TIPS ──────────────────────┐
                    </div>
                    <div style="color: #00aaff;">▸ Test PII patterns:</div>
                    <div style="margin-left: 10px; color: #666;">
                      - Emails: user@example.com<br>
                      - Phones: 555-123-4567<br>
                      - API keys: sk_live_abc123
                    </div>
                    <br>
                    <div style="color: #00aaff;">▸ Watch real-time updates</div>
                    <div style="margin-left: 10px; color: #666;">Risk chart updates per character</div>
                    <br>
                    <div style="color: #00aaff;">▸ Stream break trigger</div>
                    <div style="margin-left: 10px; color: #666;">Pause 3s to process buffer</div>
                    <br>
                    <div style="color: #00aaff;">▸ Interrupt protection</div>
                    <div style="margin-left: 10px; color: #666;">Type during response to cancel</div>
                    <div style="color: #ffaa00; font-weight: bold; margin-top: 8px;">
                    └───────────────────────────────────┘
                    </div>
                </div>
                ''')

        # Event handlers

        # User typing (fires on every character change)
        user_input.change(
            fn=lambda text: on_user_type(text, state),
            inputs=user_input,
            outputs=[risk_indicators, risk_chart, status],
        )

        # Timer for stream break detection (checks every 500ms)
        timer = gr.Timer(value=0.5)
        timer.tick(
            fn=lambda: check_and_process_buffer(state),
            outputs=[original_display, masked_display, assistant_display, status],
        )

        # Clear button
        clear_btn.click(
            fn=lambda: clear_conversation(state),
            outputs=[
                user_input,
                risk_indicators,
                risk_chart,
                status,
                original_display,
                masked_display,
                assistant_display,
            ],
        )

    return demo
