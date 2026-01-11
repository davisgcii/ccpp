"""Main Gradio application for PII-masked chat GUI (professional design)."""

import time
import logging
import gradio as gr

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/gui_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

    Args:
        current_text: Full text in the current display box (may include "User:\n" prefix and "Assistant: " content)
        state: Application state

    Returns:
        Tuple of (user_input_hidden, risk_html, risk_chart, status_text)
    """
    # Extract user input (text after "User:\n" and before any "Assistant:" if present)
    user_input = ""
    if current_text.startswith("User:\n"):
        text_after_user = current_text[6:]  # Remove "User:\n" prefix
        # Check if there's an "Assistant:" marker
        if "\nAssistant: " in text_after_user:
            user_input = text_after_user.split("\nAssistant: ")[0]
        else:
            user_input = text_after_user
    elif current_text.startswith("User: "):  # Fallback for old format
        text_after_user = current_text[6:]  # Remove "User: " prefix
        if "\nAssistant: " in text_after_user:
            user_input = text_after_user.split("\nAssistant: ")[0]
        else:
            user_input = text_after_user
    else:
        user_input = current_text

    logger.info(f"[on_user_type] Received text: {repr(user_input[:50])}{'...' if len(user_input) > 50 else ''}")

    with state.lock:
        # If currently processing LLM response, mark for interruption
        if state.is_processing:
            logger.info("[on_user_type] Marking for interruption (LLM is processing)")
            state.should_interrupt = True

        # Update buffer and timing
        state.buffer = user_input
        state.last_input_time = time.time()
        logger.debug(f"[on_user_type] Buffer updated, length={len(user_input)}, last_input_time={state.last_input_time}")

        # Clear risk history if text is empty
        if not user_input:
            state.risk_history = []
            state.current_char_data = []
            return (
                "",  # user_input_hidden
                create_risk_html("", []),
                create_risk_chart([]),
                format_status(),
            )

        # Process through Stage 1 (per-character classification)
        risk_score = state.stage1.classify(state.conversation, user_input)
        logger.debug(f"[on_user_type] Stage1 risk_score: {risk_score.score:.3f}, top_category: {risk_score.top_category}")

        # Update EMA
        should_escalate = state.guard.risk_state.update(risk_score.score)
        ema = state.guard.risk_state.ema_risk  # Get the actual EMA value from state
        any_risk = risk_score.score >= state.guard.risk_threshold_immediate
        logger.debug(f"[on_user_type] EMA updated: {ema:.3f}, should_escalate: {should_escalate}, any_risk: {any_risk}, risk_history_len: {len(state.risk_history)}")

        # CRITICAL: Update guard's flag if this character is high-risk
        # This flag persists until reset at stream break, tracking if ANY token in buffer was risky
        if any_risk:
            state.guard.any_risk_in_buffer = True
            logger.debug(f"[on_user_type] Set any_risk_in_buffer=True (current char is high-risk)")

        # Build CharClassification for this character (for tooltip debugging)
        current_char = user_input[-1] if user_input else ""
        char_idx = len(user_input) - 1

        # Get classifier prompt (simplified for mock mode)
        classifier_prompt = state.stage1._format_prompt_with_few_shot(state.conversation, user_input) if hasattr(state.stage1, '_format_prompt_with_few_shot') else []

        char_classification = CharClassification(
            char=current_char,
            idx=char_idx,
            risk_score=risk_score.score,
            ema=ema,
            classifier_prompt=classifier_prompt,
            classifier_response={
                "p_risk": risk_score.score,
                "p_safe": 1.0 - risk_score.score,
                "raw_output": f"RISK {risk_score.score:.3f}",
            },
            timestamp=time.time(),
        )

        # Store character data
        state.current_char_data.append(char_classification)

        # Add to risk history
        risk_entry = {
            'char_idx': char_idx,
            'p_risk': risk_score.score,
            'ema': ema,
            'any_risk': any_risk,
        }
        state.risk_history.append(risk_entry)
        logger.debug(f"[on_user_type] Added risk_history entry: char_idx={char_idx}, p_risk={risk_score.score:.3f}, ema={ema:.3f}")

        # Generate outputs
        risk_html = create_risk_html(
            user_input,
            state.risk_history,
            threshold=state.guard.risk_threshold_immediate,
        )
        risk_chart = create_risk_chart(
            state.risk_history,
            t_high=state.t_high,
            t_low=state.t_low,
        )
        status_text = format_status()

        return user_input, risk_html, risk_chart, status_text


def check_and_process_buffer(state: PIIClientState):
    """Check for stream break and process buffer if ready.

    Args:
        state: Application state

    Returns:
        Tuple of (history_html, current_display, original_text, masked_text, assistant_text, status_text)
    """
    # Check if we should process
    logger.debug("[check_and_process_buffer] Timer tick - checking buffer...")
    if not state.should_process_buffer():
        logger.debug("[check_and_process_buffer] Not ready to process, returning")
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

    logger.info("[check_and_process_buffer] STREAM BREAK DETECTED - Processing buffer!")

    try:
        with state.lock:
            # Mark as processing
            state.is_processing = True
            state.should_interrupt = False

            # Get original text
            original_text = state.buffer
            logger.info(f"[check_and_process_buffer] Processing buffer of length {len(original_text)}")
            logger.debug(f"[check_and_process_buffer] Buffer text: {repr(original_text[:150])}")

            # Decide if we need to mask based on already-computed risk scores
            # We already ran Stage 1 on every character during typing, so we can use that
            should_mask = False
            ema_risk = state.guard.risk_state.ema_risk
            any_risk = state.guard.any_risk_in_buffer  # This is on guard, not risk_state

            logger.info(f"[check_and_process_buffer] ema_risk={ema_risk:.3f}, any_risk={any_risk}, t_high={state.t_high}")

            if any_risk or ema_risk >= state.t_high:
                should_mask = True
                logger.info("[check_and_process_buffer] Masking needed - calling Stage 2")

            # Check heuristics for strong matches
            heuristic_matches = state.heuristics.detect(original_text)
            logger.debug(f"[check_and_process_buffer] Heuristic matches: {len(heuristic_matches)} found")
            if state.heuristics.has_strong_match(heuristic_matches):
                should_mask = True
                logger.info(f"[check_and_process_buffer] Strong heuristic match: {[m.pattern_name for m in heuristic_matches]}")
            else:
                logger.debug(f"[check_and_process_buffer] No strong heuristic matches (found {len(heuristic_matches)} total)")

            masked_text = original_text

            if should_mask:
                # Call Stage 2 to get entity extractions
                logger.info("[check_and_process_buffer] Calling Stage 2 for entity extraction")
                stage2_result = state.stage2.redact(
                    messages=state.conversation,
                    window_text=original_text,
                )
                logger.info(f"[check_and_process_buffer] Stage 2 result: {stage2_result}")

                # Apply masks
                if stage2_result.spans:
                    for span in stage2_result.spans:
                        mask_str = f"[{span.category.value.upper().replace('/', '/')}]"
                        masked_text = masked_text.replace(span.entity_text, mask_str)
                        logger.info(f"[check_and_process_buffer] Masked '{span.entity_text}' -> '{mask_str}'")
                else:
                    logger.info("[check_and_process_buffer] Stage 2 returned no entities to mask")
            else:
                logger.info("[check_and_process_buffer] No masking needed - passing through")

            logger.info(f"[check_and_process_buffer] FLOW: Post-masking - original_len={len(original_text)}, masked_len={len(masked_text)}, was_masked={original_text != masked_text}")

            # Mark buffer as processed
            state.processed_buffer = state.buffer
            logger.debug("[check_and_process_buffer] FLOW: Marked buffer as processed")

            # Build BufferMetadata for this exchange
            was_masked = original_text != masked_text
            logger.debug(f"[check_and_process_buffer] FLOW: Building metadata - was_masked={was_masked}, char_data_len={len(state.current_char_data)}, risk_history_len={len(state.risk_history)}")

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
            logger.info(f"[check_and_process_buffer] FLOW: Added user message to conversation - conv_len={len(state.conversation)}, content_preview={masked_text[:50]}")

            # Clear character data for next buffer
            state.current_char_data = []

            # Reset any_risk_in_buffer flag for next buffer
            state.guard.any_risk_in_buffer = False
            logger.debug("[check_and_process_buffer] Reset any_risk_in_buffer=False for next buffer")

        # Call LLM (if available) - do this outside the lock
        assistant_text = ""
        logger.info(f"[check_and_process_buffer] FLOW: Exited lock - about to call LLM (anthropic={'available' if state.anthropic else 'unavailable'})")

        if state.anthropic:
            try:
                logger.info(f"[check_and_process_buffer] FLOW: Calling LLM with {len(state.conversation)} messages")
                # Make synchronous call to Claude
                response = state.anthropic.messages.create(
                    model=ApprovedModel.CLAUDE_HAIKU_4_5.value,
                    max_tokens=1024,
                    messages=state.conversation,
                )

                logger.info(f"[check_and_process_buffer] FLOW: LLM call completed - response_len={len(response.content[0].text) if response.content else 0}")

                # Check if interrupted during call
                if state.should_interrupt:
                    # User started typing - don't add response to history
                    assistant_text = "[Response interrupted - user started typing]"
                    logger.info("[check_and_process_buffer] FLOW: Response interrupted by user typing")
                else:
                    # Complete response
                    assistant_text = response.content[0].text
                    logger.info(f"[check_and_process_buffer] FLOW: Adding assistant response to conversation - preview={assistant_text[:50]}")

                    # Add to conversation history
                    state.add_to_conversation({
                        "role": "assistant",
                        "content": assistant_text,
                    })

            except Exception as e:
                assistant_text = f"[LLM error: {e}]"
                logger.error(f"[check_and_process_buffer] FLOW: LLM call failed - error={e}", exc_info=True)

        else:
            assistant_text = "[LLM unavailable - no API key]"
            logger.info("[check_and_process_buffer] FLOW: LLM unavailable - no API key set")

        logger.info(f"[check_and_process_buffer] FLOW: Building final UI updates - assistant_text_len={len(assistant_text)}")

        # Update status
        status_text = format_status(
            is_processing=False,
            chars_processed=len(original_text),
            chars_masked=len(masked_text),
        )

        # Generate updated history HTML
        history_html = create_conversation_history_html(state.conversation)

        # Build current_display with "User:\n" prefix (ready for next input)
        current_text = "User:\n"

        # Mark processing complete
        state.is_processing = False

        logger.info(f"[check_and_process_buffer] FLOW: Returning UI updates - history_len={len(history_html)}, current_text='{current_text}', original_len={len(original_text)}, masked_len={len(masked_text)}, assistant_len={len(assistant_text)}, status_len={len(status_text)}")

        return history_html, current_text, original_text, masked_text, assistant_text, status_text
    except Exception as e:
        logger.error(f"[check_and_process_buffer] ERROR during processing: {e}", exc_info=True)
        with state.lock:
            state.is_processing = False
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()


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
        "User:\n",  # current_display
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

            # Current conversation (combined input + streaming response)
            current_display = gr.Textbox(
                label="Current",
                value="User:\n",
                lines=8,
                interactive=True,
                show_label=True,
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

        # Timer for stream break detection
        timer = gr.Timer(value=0.5)
        timer.tick(
            fn=lambda: check_and_process_buffer(state),
            outputs=[conversation_history, current_display, original_display, masked_display, assistant_display, status],
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
