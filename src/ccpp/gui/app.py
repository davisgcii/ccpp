"""Main Gradio application for PII-masked chat GUI."""

import time
import gradio as gr

from ccpp.gui.state import PIIClientState
from ccpp.gui.components import create_risk_html, create_risk_chart, format_status
from ccpp.types import ApprovedModel


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
    """Create Gradio interface for PII-masked chat.

    Args:
        state: Application state instance

    Returns:
        Gradio Blocks interface
    """
    with gr.Blocks(
        title="PII-Masked Chat",
        theme=gr.themes.Soft(),
        css="""
        .risk-high { background-color: #ffcccc; border-bottom: 2px solid red; }
        .status-box { font-weight: bold; }
        """,
    ) as demo:
        # Header
        gr.Markdown(
            """
            # 🔒 PII-Masked Chat Client

            Real-time PII detection and masking with live risk visualization.

            **How it works:**
            1. 💬 Type your message - risk metrics update in real-time
            2. ⏸️ Pause for 3 seconds - system detects stream break
            3. 🔒 Message is automatically masked and sent to Claude
            4. 🤖 Response streams back
            5. ⚠️ Type during response to interrupt (only displayed portion saved)
            """
        )

        with gr.Row():
            # Left column: Input and outputs
            with gr.Column(scale=2):
                # User input area
                user_input = gr.Textbox(
                    label="💬 Type your message",
                    placeholder="Start typing... (e.g., 'My email is john@example.com')",
                    lines=3,
                    interactive=True,
                    elem_classes=["user-input-box"],
                )

                # Risk indicators
                risk_indicators = gr.HTML(
                    label="⚠️ Risk Indicators",
                    value=create_risk_html("", []),
                )

                # Status bar
                status = gr.Textbox(
                    label="📊 Status",
                    value=format_status(),
                    interactive=False,
                    elem_classes=["status-box"],
                )

                # Original vs Masked comparison
                gr.Markdown("### 📝 Original vs 🔒 Masked Comparison")
                with gr.Row():
                    original_display = gr.Textbox(
                        label="📝 Original Text",
                        interactive=False,
                        lines=3,
                        placeholder="Original text will appear here after stream break...",
                    )
                    masked_display = gr.Textbox(
                        label="🔒 Masked Text (sent to LLM)",
                        interactive=False,
                        lines=3,
                        placeholder="Masked text will appear here after stream break...",
                    )

                # Assistant response
                assistant_display = gr.Textbox(
                    label="🤖 Assistant Response",
                    interactive=False,
                    lines=6,
                    placeholder="Assistant response will appear here...",
                )

                # Control buttons
                with gr.Row():
                    clear_btn = gr.Button("🗑️ Clear Conversation", variant="secondary")

            # Right column: Risk chart and legend
            with gr.Column(scale=1):
                # Risk chart
                risk_chart = gr.Plot(
                    label="📈 Real-Time Risk Metrics",
                    value=create_risk_chart([]),
                )

                # Legend and explanation
                gr.Markdown(
                    """
                    ### 📊 Chart Legend

                    **Lines:**
                    - 🔵 **Blue**: P(RISK) per character
                      Raw risk score for each character
                    - 🟢/🔴 **Green/Red**: EMA (smoothed)
                      Exponential moving average of risk
                      Turns red when crossing threshold

                    **Thresholds:**
                    - 🟠 **Orange dashed**: T_high (0.6)
                      Escalation threshold
                    - ⚪ **Gray dotted**: T_low (0.3)
                      De-escalation threshold

                    **Behavior:**
                    - When EMA ≥ T_high → Escalated (red)
                    - When EMA ≤ T_low → De-escalated (green)
                    - Red highlights = P(RISK) ≥ 0.7
                    """
                )

                # Usage tips
                gr.Markdown(
                    """
                    ### 💡 Tips

                    - Try typing PII like emails, phone numbers, API keys
                    - Watch risk metrics update in real-time
                    - Pause 3 seconds to trigger processing
                    - Start typing during response to interrupt
                    - Check original vs masked to see what changed
                    """
                )

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
