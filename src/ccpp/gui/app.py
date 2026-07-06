"""Main Gradio application for PII-masked chat GUI (professional design)."""

import time
import logging
import gradio as gr

# Configure logging using centralized config
from ccpp.config import load_config
from ccpp.logging_config import configure_from_config, get_logger

# Load config and configure logging
_config = load_config()
configure_from_config(_config)
logger = get_logger(__name__)

from ccpp.gui.state import PIIClientState
from ccpp.gui.components import (
    create_risk_html,
    create_risk_chart,
    format_status,
    create_conversation_history_html,
)
from ccpp.types import ApprovedModel, CharClassification, BufferMetadata


# Professional CSS
PROFESSIONAL_CSS = """
/* Professional dark theme */
body {
    background-color: #0d0d0d !important;
}

.gradio-container {
    background-color: #0d0d0d !important;
    font-family: 'Courier New', monospace !important;
}

/* Clean textboxes */
textarea {
    font-family: 'Courier New', monospace !important;
    background-color: #1a1a1a !important;
    color: #ddd !important;
    border: 1px solid #333 !important;
    border-radius: 3px !important;
}

textarea:focus {
    border-color: #555 !important;
    box-shadow: none !important;
}

/* Labels */
label {
    color: #aaa !important;
    font-family: 'Courier New', monospace !important;
    font-size: 13px !important;
    font-weight: normal !important;
}

/* Buttons */
button {
    background-color: #2a2a2a !important;
    color: #ccc !important;
    border: 1px solid #444 !important;
    font-family: 'Courier New', monospace !important;
}

button:hover {
    background-color: #333 !important;
    border-color: #555 !important;
}

/* Hoverable tooltips */
.hoverable {
    position: relative;
    cursor: help;
    border-bottom: 1px dotted #666;
}

.hoverable:hover {
    background-color: #2a2a2a !important;
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
    color: #eee !important;
    font-family: 'Courier New', monospace !important;
}
"""


def on_user_type(current_text: str, state: PIIClientState):
    """Handle user typing event (fires on every character change).

    This function is FAST and NON-BLOCKING. It only:
    1. Updates the buffer
    2. Queues classifications for new words (spaces)
    3. Returns immediately

    Classifications are processed by the timer via process_pending_classifications().

    Args:
        current_text: The user's input text (no prefix - label is hardcoded separately)
        state: Application state

    Returns:
        Tuple of (user_input_hidden, risk_html, risk_chart, status_text)
    """
    from ccpp.logging_config import TRACE
    user_input = current_text

    with state.lock:
        # Update buffer and timing
        prev_len = len(state.buffer)
        state.buffer = user_input
        state.last_input_time = time.time()

        # Only log buffer changes at TRACE level (very verbose)
        if len(user_input) != prev_len:
            logger.log(TRACE, f"[typing] buf={len(user_input)}ch delta={len(user_input) - prev_len:+d}")

        # Clear state if text is empty
        if not user_input:
            state.risk_history = []
            state.current_char_data = []
            state.last_classified_len = 0
            state.pending_classifications = []
            return (
                "",  # user_input_hidden
                create_risk_html("", []),
                create_risk_chart([]),
                format_status(),
            )

        # Handle deletions: if text got shorter, adjust last_classified_len and clear stale pending
        if len(user_input) < state.last_classified_len:
            state.last_classified_len = len(user_input)
            # Remove any pending classifications that are now past the buffer end
            state.pending_classifications = [
                (pos, text, conv) for pos, text, conv in state.pending_classifications
                if pos < len(user_input)
            ]

        # Find ALL new spaces since last classification (or last queued position)
        # Consider both last_classified_len and any pending classifications
        last_queued_pos = state.last_classified_len
        if state.pending_classifications:
            last_queued_pos = max(last_queued_pos, max(pos for pos, _, _ in state.pending_classifications) + 1)

        new_portion = user_input[last_queued_pos:]
        space_positions = [i + last_queued_pos for i, c in enumerate(new_portion) if c == " "]

        # Queue new classifications (don't run them here - timer will process)
        if space_positions:
            conversation_snapshot = list(state.conversation)
            for space_pos in space_positions:
                text_to_classify = user_input[:space_pos + 1]
                state.pending_classifications.append((space_pos, text_to_classify, conversation_snapshot))

        # Generate UI output using current state
        risk_html = create_risk_html(
            user_input,
            state.risk_history,
            threshold=state.guard.risk_threshold_immediate,
        )
        combined_history = state.archived_risk_history + state.risk_history
        risk_chart = create_risk_chart(
            combined_history,
            t_high=state.t_high,
            t_low=state.t_low,
        )

        return user_input, risk_html, risk_chart, format_status()


def process_pending_classifications(state: PIIClientState) -> bool:
    """Process ONE pending classification from the queue.

    Called by the timer. Processes one classification at a time to stay responsive.

    Args:
        state: Application state

    Returns:
        True if a classification was processed, False if queue was empty
    """
    # Get next pending classification (if any)
    with state.lock:
        if not state.pending_classifications:
            return False

        # Take the first pending item
        space_pos, text_to_classify, conversation_snapshot = state.pending_classifications.pop(0)

        # Check if this classification is still relevant (buffer still starts with this text)
        if not state.buffer.startswith(text_to_classify[:space_pos] if space_pos > 0 else ""):
            # Buffer changed, skip this stale classification
            logger.debug(f"[classify] skipping stale classification at pos={space_pos}")
            return True  # Return True to indicate we processed (skipped) an item

        state.is_classifying = True

    # Run classification WITHOUT holding lock
    classify_start = time.time()
    try:
        risk_score = state.stage1.classify(conversation_snapshot, text_to_classify)
        latency_ms = int((time.time() - classify_start) * 1000)

        logger.info(
            f"[classify] pos={space_pos} risk={risk_score.score:.3f} "
            f"lat={latency_ms}ms text={repr(text_to_classify[-25:])}"
        )
    except Exception as e:
        logger.error(f"[classify] failed at pos={space_pos}: {e}")
        with state.lock:
            state.is_classifying = False
        return True

    # Apply result back to state
    with state.lock:
        state.is_classifying = False

        # Check if buffer still starts with what we classified
        if not state.buffer.startswith(text_to_classify):
            logger.warning("[classify] buffer changed during classification, discarding result")
            return True

        # Update EMA
        should_escalate = state.guard.risk_state.update(risk_score.score)
        ema = state.guard.risk_state.ema_risk
        any_risk = bool(risk_score.score >= state.guard.risk_threshold_immediate)

        # Update guard's flag if high-risk
        if any_risk:
            state.guard.any_risk_in_buffer = True

        # Build CharClassification
        classifier_prompt = state.stage1._build_prompt(conversation_snapshot, text_to_classify) if hasattr(state.stage1, '_build_prompt') else []

        char_classification = CharClassification(
            char=" ",
            idx=int(space_pos),
            risk_score=float(risk_score.score),
            ema=float(ema),
            classifier_prompt=classifier_prompt,
            classifier_response={
                "p_risk": float(risk_score.score),
                "p_safe": float(1.0 - risk_score.score),
                "raw_output": f"P(FAIL)={risk_score.score:.3f}",
            },
            timestamp=time.time(),
        )
        state.current_char_data.append(char_classification)

        # Add to risk history
        risk_entry = {
            'char_idx': int(space_pos),
            'p_risk': float(risk_score.score),
            'ema': float(ema),
            'any_risk': any_risk,
        }
        state.risk_history.append(risk_entry)

        # Update last_classified_len
        state.last_classified_len = max(state.last_classified_len, space_pos + 1)

        logger.debug(f"[classify_applied] pos={space_pos} ema={ema:.3f}")

    return True


def timer_tick(state: PIIClientState):
    """Main timer tick handler - processes classifications and checks for stream break.

    Called every 500ms by Gradio timer. This function:
    1. Processes ONE pending classification (if any)
    2. Then checks if stream break should trigger

    Args:
        state: Application state

    Returns:
        Tuple of UI updates
    """
    # First, process any pending classifications (one per tick to stay responsive)
    if process_pending_classifications(state):
        # A classification was processed, update the UI
        with state.lock:
            risk_html = create_risk_html(
                state.buffer,
                state.risk_history,
                threshold=state.guard.risk_threshold_immediate,
            )
            combined_history = state.archived_risk_history + state.risk_history
            risk_chart = create_risk_chart(
                combined_history,
                t_high=state.t_high,
                t_low=state.t_low,
            )
        # Return updated chart but don't trigger stream break yet
        # (let the next tick check for stream break)
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), risk_chart, risk_html

    # No pending classifications, check for stream break
    return check_and_process_buffer(state)


def check_and_process_buffer(state: PIIClientState):
    """Check for stream break and process buffer if ready.

    Args:
        state: Application state

    Returns:
        Tuple of (history_html, current_display, original_text, masked_text, assistant_text,
                  status_text, risk_chart_html, risk_indicators_html)
    """
    # Check if we should process (logging handled inside should_process_buffer)
    if not state.should_process_buffer():
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

    # Calculate elapsed time for stream break log
    elapsed = time.time() - state.last_input_time if state.last_input_time else 0
    logger.info(
        f"[STREAM_BREAK] buf={len(state.buffer)}ch wait={elapsed:.1f}s "
        f"text={repr(state.buffer[:40])}{'...' if len(state.buffer) > 40 else ''}"
    )

    try:
        with state.lock:
            # Mark as processing
            state.is_processing = True
            state.should_interrupt = False

            # Get original text
            original_text = state.buffer

            # If there's unclassified text at the end (user didn't end with space),
            # run one final classification on the full buffer before making masking decision
            final_risk_score = None
            if len(original_text) > state.last_classified_len:
                unclassified_len = len(original_text) - state.last_classified_len

                state.is_classifying = True
                classify_start = time.time()
                try:
                    risk_score = state.stage1.classify(state.conversation, original_text)
                finally:
                    state.is_classifying = False
                classify_ms = int((time.time() - classify_start) * 1000)
                final_risk_score = risk_score.score

                # Update EMA and risk tracking
                state.guard.risk_state.update(risk_score.score)
                ema = state.guard.risk_state.ema_risk
                any_risk = bool(risk_score.score >= state.guard.risk_threshold_immediate)

                if any_risk:
                    state.guard.any_risk_in_buffer = True

                # Add to risk history
                risk_entry = {
                    'char_idx': len(original_text) - 1,
                    'p_risk': float(risk_score.score),
                    'ema': float(ema),
                    'any_risk': any_risk,
                }
                state.risk_history.append(risk_entry)
                state.last_classified_len = len(original_text)

                logger.debug(f"[classify_final] unclassified={unclassified_len}ch risk={risk_score.score:.3f} ema={ema:.3f} lat={classify_ms}ms")

            # Decide if we need to mask based on already-computed risk scores
            should_mask = False
            ema_risk = state.guard.risk_state.ema_risk
            any_risk = state.guard.any_risk_in_buffer  # This is on guard, not risk_state

            if any_risk or ema_risk >= state.t_high:
                should_mask = True

            # Check heuristics for strong matches
            heuristic_matches = state.heuristics.detect(original_text)
            strong_heuristic = state.heuristics.has_strong_match(heuristic_matches)
            if strong_heuristic:
                should_mask = True

            masked_text = original_text
            stage2_entities = 0

            if should_mask:
                # Call Stage 2 to get entity extractions
                stage2_start = time.time()
                stage2_result = state.stage2.redact(
                    messages=state.conversation,
                    window_text=original_text,
                )
                stage2_ms = int((time.time() - stage2_start) * 1000)
                stage2_entities = len(stage2_result.spans)

                # Apply masks
                if stage2_result.spans:
                    for span in stage2_result.spans:
                        mask_str = f"[{span.category.value.upper().replace('/', '/')}]"
                        masked_text = masked_text.replace(span.entity_text, mask_str)

                logger.info(f"[STAGE2] entities={stage2_entities} lat={stage2_ms}ms result={stage2_result}")

            was_masked = original_text != masked_text

            # Consolidated decision log
            logger.info(
                f"[DECISION] ema={ema_risk:.3f} any_risk={any_risk} heuristic={strong_heuristic} "
                f"will_mask={should_mask} was_masked={was_masked}"
            )

            # Mark buffer as processed
            state.processed_buffer = state.buffer

            # Build BufferMetadata for this exchange

            # Create simplified masker data (for now, since we're using guard internally)
            masker_prompt = None  # Would be populated if we call stage2 directly
            masker_response = None
            if was_masked:
                masker_response = {
                    "raw_output": f"Masked {len(original_text) - len(masked_text)} characters",
                    "entities": [],  # Would contain extracted entities
                }

            buffer_metadata = BufferMetadata(
                original_text=original_text,
                masked_text=masked_text,
                char_data=state.current_char_data.copy(),  # Copy current character data
                masker_prompt=masker_prompt,
                masker_response=masker_response,
                risk_history=state.risk_history.copy(),  # Copy risk history for mini-chart
                heuristic_matches=[],  # Would contain heuristic matches
                was_masked=was_masked,
                timestamp=time.time(),
            )

            # Store in state for reference
            state.current_buffer_metadata = buffer_metadata

            # Add user message to conversation with metadata
            user_message = {
                "role": "user",
                "content": masked_text,
                "metadata": buffer_metadata.to_dict(),
            }
            state.add_to_conversation(user_message)

            # Clear ALL history for fresh chart on next buffer
            archived_count = len(state.archived_risk_history)
            state.current_char_data = []
            state.risk_history = []  # Reset for next buffer
            state.archived_risk_history = []  # Clear archive so chart resets
            state.last_classified_len = 0  # Reset for next buffer

            # NOTE: EMA state is NOT reset - it persists across buffers for cross-break detection
            # per CLAUDE.md design. Only reset any_risk_in_buffer flag.
            state.guard.any_risk_in_buffer = False

            logger.debug(f"[buffer_reset] archived={archived_count} conv_len={len(state.conversation)}")

        # Call LLM (if available) - do this outside the lock
        assistant_text = ""

        if state.anthropic:
            try:
                # Strip metadata for API call (Anthropic only accepts role/content)
                api_messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in state.conversation
                ]
                from ccpp.llm.prompt_logger import log_prompt_event
                # Make synchronous call to Claude with timing
                start_time = time.time()
                response = state.anthropic.messages.create(
                    model=ApprovedModel.CLAUDE_HAIKU_4_5.value,
                    max_tokens=1024,
                    messages=api_messages,
                )
                latency_ms = int((time.time() - start_time) * 1000)

                # Always complete the response - we can't interrupt synchronous calls anyway.
                # User's typing during this time will be in their buffer for the next exchange.
                assistant_text = response.content[0].text
                response_len = len(assistant_text)

                logger.info(f"[LLM] msgs={len(api_messages)} resp={response_len}ch lat={latency_ms}ms")

                # Add to conversation history
                state.add_to_conversation({
                    "role": "assistant",
                    "content": assistant_text,
                })

                log_prompt_event(
                    {
                        "backend": "anthropic",
                        "kind": "generate",
                        "model": ApprovedModel.CLAUDE_HAIKU_4_5.value,
                        "messages": api_messages,
                        "response": assistant_text,
                        "max_tokens": 1024,
                        "latency_ms": latency_ms,
                    }
                )

            except Exception as e:
                assistant_text = f"[LLM error: {e}]"
                logger.error(f"[LLM] call failed: {e}")

        else:
            assistant_text = "[LLM unavailable - no API key]"
            logger.debug("[LLM] unavailable - no API key")

        # Update status
        status_text = format_status(
            is_processing=False,
            chars_processed=len(original_text),
            chars_masked=len(masked_text),
        )

        # Generate updated history HTML
        history_html = create_conversation_history_html(state.conversation)

        # Clear input for next message (label is hardcoded separately in UI)
        current_text = ""

        # Show archived history for chart continuity (current buffer is empty)
        risk_chart_html = create_risk_chart(state.archived_risk_history)
        risk_indicators_html = create_risk_html("", [])

        # Mark processing complete
        state.is_processing = False

        return history_html, current_text, original_text, masked_text, assistant_text, status_text, risk_chart_html, risk_indicators_html
    except Exception as e:
        logger.error(f"[STREAM_BREAK] processing error: {e}")
        with state.lock:
            state.is_processing = False
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()


def clear_conversation(state: PIIClientState):
    """Clear all conversation state and reset UI.

    Args:
        state: Application state

    Returns:
        Tuple of all cleared UI elements
    """
    state.reset()

    return (
        create_conversation_history_html([]),  # conversation_history
        "",  # current_display (label is hardcoded separately)
        create_risk_html("", []),  # risk_indicators
        create_risk_chart([]),  # risk_chart
        format_status(),  # status
        "",  # user_input_hidden
        "",  # original_display
        "",  # masked_display
        "",  # assistant_display
    )


def create_gui(state: PIIClientState) -> tuple:
    """Create Gradio interface for PII-masked chat (professional design).

    Args:
        state: Application state instance

    Returns:
        Tuple of (demo, theme, css) for Gradio 6.0 compatibility
    """
    # Create simple dark theme
    theme = gr.themes.Base(
        primary_hue="slate",
        secondary_hue="slate",
        neutral_hue="slate",
    )

    # Note: In Gradio 6.0+, theme and css are passed to launch(), not Blocks()
    with gr.Blocks(title="PII Masking Demo") as demo:
        # Simple header
        gr.HTML('''
        <div style="
            font-family: 'Courier New', monospace;
            padding: 16px;
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 3px;
            margin-bottom: 16px;">
            <h2 style="color: #ccc; margin: 0; font-size: 18px; font-weight: normal;">
                PII Masking Demo
            </h2>
            <p style="color: #888; margin: 8px 0 0 0; font-size: 13px;">
                Real-time detection and masking • Stream break: 3s pause • Type to interrupt responses
            </p>
        </div>
        ''')

        # SECTION 1: Conversation History (scrollable, top)
        conversation_history = gr.HTML(
            label="Conversation History",
            value=create_conversation_history_html([]),
        )

        gr.HTML('<div style="height: 20px;"></div>')  # Spacer

        # SECTION 2: Active I/O (middle)
        with gr.Group():
            gr.HTML('''
            <div style="
                font-family: 'Courier New', monospace;
                font-size: 11px;
                color: #888;
                margin-bottom: 8px;">
                ACTIVE SESSION
            </div>
            ''')

            # User label (hardcoded, not editable)
            gr.HTML('''
            <div style="
                font-family: 'Courier New', monospace;
                font-size: 14px;
                color: #aaa;
                padding: 4px 0;">
                User:
            </div>
            ''')

            # User input (clean text only - no "User:" prefix)
            current_display = gr.Textbox(
                label=None,  # Label is provided by HTML above
                value="",
                lines=4,
                interactive=True,
                show_label=False,
                placeholder="Type your message here...",
            )

            # Status
            status = gr.HTML(
                label="Status",
                value=format_status(),
            )

        gr.HTML('<div style="height: 20px;"></div>')  # Spacer

        # SECTION 3: Chart (bottom)
        risk_chart = gr.HTML(
            label="Risk Metrics (Real-time)",
            value=create_risk_chart([]),
        )

        # Hidden elements (not displayed but needed for state)
        risk_indicators = gr.HTML(visible=False, value=create_risk_html("", []))
        user_input_hidden = gr.Textbox(visible=False, value="")  # Track just user input
        original_display = gr.Textbox(visible=False, value="")
        masked_display = gr.Textbox(visible=False, value="")
        assistant_display = gr.Textbox(visible=False, value="")

        # Clear button
        clear_btn = gr.Button("Clear Conversation", variant="secondary")

        # Event handlers

        # User typing - use .input() for per-keystroke updates, not .change()
        current_display.input(
            fn=lambda text: on_user_type(text, state),
            inputs=current_display,
            outputs=[user_input_hidden, risk_indicators, risk_chart, status],
        )

        # Timer for classification processing and stream break detection
        timer = gr.Timer(value=0.5)
        timer.tick(
            fn=lambda: timer_tick(state),
            outputs=[conversation_history, current_display, original_display, masked_display, assistant_display, status, risk_chart, risk_indicators],
        )

        # Clear button
        clear_btn.click(
            fn=lambda: clear_conversation(state),
            outputs=[
                conversation_history,
                current_display,
                risk_indicators,
                risk_chart,
                status,
                user_input_hidden,
                original_display,
                masked_display,
                assistant_display,
            ],
        )

    return demo, theme, PROFESSIONAL_CSS
