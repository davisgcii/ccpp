"""Main NiceGUI application for PII-masked chat (Apple Design)."""

from __future__ import annotations

import time
import logging

from nicegui import ui, run

from ccpp.config import load_config
from ccpp.logging_config import configure_from_config, get_logger, TRACE
from ccpp.gui.state import PIIClientState
from ccpp.types import ApprovedModel, CharClassification, BufferMetadata

from ccpp.nicegui.styles import COLORS, FONT_STACK, GLOBAL_CSS
from ccpp.nicegui.components import (
    ConversationPanel,
    ReviewPanel,
    RiskChart,
    SessionSparkline,
    StatusIndicator,
    TextHighlightOverlay,
)

logger = get_logger(__name__)


def process_pending_classifications(state: PIIClientState, session: dict) -> bool:
    """Process ONE pending classification from the queue.

    NiceGUI version: identical to the Gradio version except each risk_history
    entry includes a ``buffer`` field with the text that was classified,
    and uses a running word offset so the chart x-axis is continuous.
    """
    with state.lock:
        if not state.pending_classifications:
            return False

        space_pos, text_to_classify, conversation_snapshot = state.pending_classifications.pop(0)

        if not state.buffer.startswith(text_to_classify[:space_pos] if space_pos > 0 else ""):
            logger.debug(f"[classify] skipping stale classification at pos={space_pos}")
            return True

        state.is_classifying = True

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

    with state.lock:
        state.is_classifying = False

        if not state.buffer.startswith(text_to_classify):
            logger.warning("[classify] buffer changed during classification, discarding result")
            return True

        should_escalate = state.guard.risk_state.update(risk_score.score)
        ema = state.guard.risk_state.ema_risk
        any_risk = bool(risk_score.score >= state.guard.risk_threshold_immediate)

        if any_risk:
            state.guard.any_risk_in_buffer = True

        classifier_prompt = (
            state.stage1._format_prompt_with_few_shot(conversation_snapshot, text_to_classify)
            if hasattr(state.stage1, "_format_prompt_with_few_shot")
            else []
        )

        char_classification = CharClassification(
            char=" ",
            idx=int(space_pos),
            risk_score=float(risk_score.score),
            ema=float(ema),
            classifier_prompt=classifier_prompt,
            classifier_response={
                "p_risk": float(risk_score.score),
                "p_safe": float(1.0 - risk_score.score),
                "raw_output": f"RISK {risk_score.score:.3f}",
            },
            timestamp=time.time(),
        )
        state.current_char_data.append(char_classification)

        # Use word index with running offset so chart is continuous across utterances
        local_word_idx = len(text_to_classify.split()) - 1
        word_idx = session["word_offset"] + local_word_idx

        risk_entry = {
            "char_idx": word_idx,
            "p_risk": float(risk_score.score),
            "ema": float(ema),
            "any_risk": any_risk,
            "buffer": text_to_classify,
        }
        state.risk_history.append(risk_entry)

        state.last_classified_len = max(state.last_classified_len, space_pos + 1)
        logger.debug(f"[classify_applied] pos={space_pos} ema={ema:.3f}")

    return True


def create_app(state: PIIClientState) -> None:
    """Define the NiceGUI page and wire up all event handlers.

    Args:
        state: Shared PIIClientState instance (same as Gradio version uses).
    """

    # ── Shared mutable refs for closures ──
    _components: dict = {}
    # Running word offset so the chart x-axis is continuous across utterances.
    # Also track past utterances for the left-panel highlight display.
    _session: dict = {"word_offset": 0, "utterances": []}

    # ── Event handlers ────────────────────────────────────────────────

    def on_user_type(e) -> None:
        """Per-keystroke handler. Fast and non-blocking — queues work for timer."""
        # NiceGUI on_change passes ValueChangeEventArguments with .value
        current_text = e.value if hasattr(e, "value") else str(e)
        if current_text is None:
            current_text = ""

        logger.info(f"[on_user_type] len={len(current_text)} text={repr(current_text[-30:])}")

        with state.lock:
            prev_len = len(state.buffer)
            state.buffer = current_text
            state.last_input_time = time.time()

            if len(current_text) != prev_len:
                logger.log(TRACE, f"[typing] buf={len(current_text)}ch delta={len(current_text) - prev_len:+d}")

            if not current_text:
                state.risk_history = []
                state.current_char_data = []
                state.last_classified_len = 0
                state.pending_classifications = []
                # Don't clear chart or highlight — past utterances persist
                combined = state.archived_risk_history
                _components["chart"].update(combined, t_high=state.t_high, t_low=state.t_low, risk_threshold=state.guard.risk_threshold_immediate)
                _components["highlight"].render_all(_session["utterances"], "", [])
                _components["status"].update()
                return

            # Handle deletions
            if len(current_text) < state.last_classified_len:
                state.last_classified_len = len(current_text)
                state.pending_classifications = [
                    (pos, text, conv)
                    for pos, text, conv in state.pending_classifications
                    if pos < len(current_text)
                ]

            # Queue classifications at space positions
            last_queued_pos = state.last_classified_len
            if state.pending_classifications:
                last_queued_pos = max(
                    last_queued_pos,
                    max(pos for pos, _, _ in state.pending_classifications) + 1,
                )

            new_portion = current_text[last_queued_pos:]
            space_positions = [
                i + last_queued_pos for i, c in enumerate(new_portion) if c == " "
            ]

            if space_positions:
                conversation_snapshot = list(state.conversation)
                for space_pos in space_positions:
                    text_to_classify = current_text[: space_pos + 1]
                    state.pending_classifications.append(
                        (space_pos, text_to_classify, conversation_snapshot)
                    )
                logger.info(f"[on_user_type] queued {len(space_positions)} classifications, "
                            f"pending={len(state.pending_classifications)}")

            # Update chart from current state
            combined = state.archived_risk_history + state.risk_history
            logger.info(f"[on_user_type] chart data points: {len(combined)}")
            _components["chart"].update(combined, t_high=state.t_high, t_low=state.t_low, risk_threshold=state.guard.risk_threshold_immediate)
            _components["highlight"].render_all(
                _session["utterances"],
                current_text,
                state.risk_history,
            )
            _components["status"].update(
                is_processing=state.is_processing,
                is_classifying=state.is_classifying,
            )

    def on_timer_tick() -> None:
        """500ms timer — process pending classifications only.

        MLX calls run synchronously here (not via run.io_bound) because
        Apple Silicon's Metal backend crashes when called from a thread pool.
        Each classification takes ~400ms which is acceptable for demo use.
        """
        with state.lock:
            pending_count = len(state.pending_classifications)
        if pending_count > 0:
            logger.info(f"[timer] pending={pending_count}, about to process one")

        processed = process_pending_classifications(state, _session)

        if processed:
            logger.info(f"[timer] classification processed, updating chart")
            with state.lock:
                combined = state.archived_risk_history + state.risk_history
                buf = state.buffer
            _components["chart"].update(combined, t_high=state.t_high, t_low=state.t_low, risk_threshold=state.guard.risk_threshold_immediate)
            _components["highlight"].render_all(
                _session["utterances"],
                buf,
                state.risk_history,
            )
            _components["status"].update(
                is_processing=state.is_processing,
                is_classifying=state.is_classifying,
            )

    async def on_send_click() -> None:
        """User clicked Send — classify remainder, mask, review, then send to LLM.

        Async so that long-running Stage 2 / LLM calls don't block the WebSocket.
        Stage 1 (timer) is paused via is_processing flag, so no concurrent MLX access.
        """
        with state.lock:
            if state.is_processing or not state.buffer.strip():
                return

        logger.info(
            f"[SEND] buf={len(state.buffer)}ch "
            f"text={repr(state.buffer[:40])}{'...' if len(state.buffer) > 40 else ''}"
        )

        try:
            with state.lock:
                state.is_processing = True
                state.should_interrupt = False
                original_text = state.buffer

            _components["status"].update(is_processing=True)

            # Final classification on unclassified text (outside lock for I/O)
            with state.lock:
                needs_final = len(original_text) > state.last_classified_len
                conv_snapshot = list(state.conversation)

            if needs_final:
                with state.lock:
                    state.is_classifying = True
                _components["status"].update(is_processing=True, is_classifying=True)

                risk_score = await run.io_bound(state.stage1.classify, conv_snapshot, original_text)

                with state.lock:
                    state.is_classifying = False
                    state.guard.risk_state.update(risk_score.score)
                    ema = state.guard.risk_state.ema_risk
                    any_risk = bool(risk_score.score >= state.guard.risk_threshold_immediate)
                    if any_risk:
                        state.guard.any_risk_in_buffer = True

                    local_word_idx = len(original_text.split()) - 1
                    word_idx = _session["word_offset"] + local_word_idx
                    risk_entry = {
                        "char_idx": word_idx,
                        "p_risk": float(risk_score.score),
                        "ema": float(ema),
                        "any_risk": any_risk,
                        "buffer": original_text,
                    }
                    state.risk_history.append(risk_entry)
                    state.last_classified_len = len(original_text)

            # Masking decision
            with state.lock:
                should_mask = False
                ema_risk = state.guard.risk_state.ema_risk
                any_risk_flag = state.guard.any_risk_in_buffer

                if any_risk_flag or ema_risk >= state.t_high:
                    should_mask = True

                heuristic_matches = state.heuristics.detect(original_text)
                strong_heuristic = state.heuristics.has_strong_match(heuristic_matches)
                if strong_heuristic:
                    should_mask = True

            masked_text = original_text
            stage2_result = None

            if should_mask:
                stage2_result = await run.io_bound(
                    state.stage2.redact,
                    messages=conv_snapshot,
                    window_text=original_text,
                )

                if stage2_result.spans:
                    for span in stage2_result.spans:
                        mask_str = f"[{span.category.value.upper()}]"
                        masked_text = masked_text.replace(span.entity_text, mask_str)

                logger.info(f"[STAGE2] entities={len(stage2_result.spans)} result={stage2_result}")

            was_masked = original_text != masked_text

            logger.info(
                f"[DECISION] ema={ema_risk:.3f} any_risk={any_risk_flag} "
                f"heuristic={strong_heuristic} will_mask={should_mask} was_masked={was_masked}"
            )

            # If entities were found, show review panel and wait for user action.
            # Otherwise, send directly.
            if stage2_result and stage2_result.spans:
                _components["review"].show(original_text, masked_text, stage2_result.spans)
                # The ReviewPanel's send callback will call _finalize_send
                # Store context for the callback
                _components["_pending_send"] = {
                    "original_text": original_text,
                    "stage2_result": stage2_result,
                    "ema_risk": ema_risk,
                }
                return

            # No entities or no masking needed — send immediately
            await _finalize_send(original_text, masked_text, was_masked, ema_risk, [])

        except Exception as e:
            logger.error(f"[SEND] error: {e}", exc_info=True)
            with state.lock:
                state.is_processing = False
            _components["status"].update(error=str(e))

    async def _finalize_send(
        original_text: str,
        masked_text: str,
        was_masked: bool,
        ema_risk: float,
        approved_spans: list,
    ) -> None:
        """Commit message to conversation and call LLM."""

        _components["review"].hide()

        with state.lock:
            state.processed_buffer = state.buffer

            masker_response = None
            if was_masked:
                masker_response = {
                    "raw_output": f"Masked {len(original_text) - len(masked_text)} characters",
                    "entities": [],
                }

            buffer_metadata = BufferMetadata(
                original_text=original_text,
                masked_text=masked_text,
                char_data=state.current_char_data.copy(),
                masker_prompt=None,
                masker_response=masker_response,
                risk_history=state.risk_history.copy(),
                heuristic_matches=[],
                was_masked=was_masked,
                timestamp=time.time(),
            )

            state.current_buffer_metadata = buffer_metadata

            user_message = {
                "role": "user",
                "content": masked_text,
                "metadata": buffer_metadata.to_dict(),
            }
            state.add_to_conversation(user_message)

            # Archive current risk history (chart persists across utterances)
            state.archived_risk_history.extend(state.risk_history)
            state.risk_history = []
            state.current_char_data = []
            state.last_classified_len = 0
            state.guard.any_risk_in_buffer = False

        # Advance word offset for next utterance
        word_count = len(original_text.split())
        _session["word_offset"] += word_count

        # Save utterance for left-panel highlight display
        _session["utterances"].append({
            "text": original_text,
            "risk_history": buffer_metadata.risk_history,
            "was_masked": was_masked,
        })

        # Update sparkline
        peak_risk = max(
            (r["p_risk"] for r in buffer_metadata.risk_history), default=0
        )
        _components["sparkline"].add_point(peak_risk, ema_risk)

        # Render conversation so far (user message visible)
        _components["conversation"].render(state.conversation)
        _components["input"].value = ""
        state.buffer = ""

        # Update left panel: show all past utterances + chart stays
        _components["highlight"].render_all(
            _session["utterances"],
            state.buffer,
            state.archived_risk_history + state.risk_history,
        )

        # Call LLM
        if state.anthropic:
            try:
                from ccpp.llm.prompt_logger import log_prompt_event

                with state.lock:
                    api_messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in state.conversation
                    ]

                start_time = time.time()

                response = await run.io_bound(
                    state.anthropic.messages.create,
                    model=ApprovedModel.CLAUDE_HAIKU_4_5.value,
                    max_tokens=1024,
                    system=(
                        "You are a friendly, helpful customer support agent. "
                        "Keep your responses concise — 1-3 sentences max."
                    ),
                    messages=api_messages,
                )

                assistant_text = response.content[0].text
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    f"[LLM] msgs={len(api_messages)} resp={len(assistant_text)}ch lat={latency_ms}ms"
                )

                state.add_to_conversation({
                    "role": "assistant",
                    "content": assistant_text,
                })

                log_prompt_event({
                    "backend": "anthropic",
                    "kind": "generate",
                    "model": ApprovedModel.CLAUDE_HAIKU_4_5.value,
                    "messages": api_messages,
                    "response": assistant_text,
                    "max_tokens": 1024,
                    "latency_ms": latency_ms,
                })

            except Exception as e:
                logger.error(f"[LLM] call failed: {e}")
                state.add_to_conversation({
                    "role": "assistant",
                    "content": f"[LLM error: {e}]",
                })
        else:
            state.add_to_conversation({
                "role": "assistant",
                "content": "[LLM unavailable — no API key]",
            })

        # Re-render conversation with assistant response
        _components["conversation"].render(state.conversation)

        with state.lock:
            state.is_processing = False

        _components["status"].update(
            chars_processed=len(original_text), was_masked=was_masked
        )

    async def on_review_send(approved_spans: list) -> None:
        """Called by ReviewPanel when user clicks Send."""
        pending = _components.get("_pending_send")
        if not pending:
            return

        original_text = pending["original_text"]
        ema_risk = pending["ema_risk"]

        # Re-apply masks with only approved spans
        masked_text = original_text
        for span in approved_spans:
            mask_str = f"[{span.category.value.upper()}]"
            masked_text = masked_text.replace(span.entity_text, mask_str)

        was_masked = original_text != masked_text
        await _finalize_send(original_text, masked_text, was_masked, ema_risk, approved_spans)

    def on_review_edit() -> None:
        """Called by ReviewPanel when user clicks Edit."""
        _components["review"].hide()
        with state.lock:
            state.is_processing = False
            # Reset timing so stream break doesn't fire immediately
            state.last_input_time = time.time()
        _components["status"].update()

    async def on_enter_key(e) -> None:
        """Enter submits, Shift+Enter inserts newline."""
        if e.args.get("shiftKey", False) if hasattr(e, "args") and isinstance(e.args, dict) else False:
            return  # Let Shift+Enter insert a newline normally
        # Plain Enter — prevent the newline and submit
        # Strip the trailing newline that was just inserted
        val = _components["input"].value or ""
        if val.endswith("\n"):
            _components["input"].value = val[:-1]
            state.buffer = val[:-1]

        # If the review panel is visible, confirm it instead of starting a new send
        if _components["review"].panel.visible:
            approved = _components["review"].get_approved_spans()
            await on_review_send(approved)
            return

        await on_send_click()

    def on_clear() -> None:
        """Reset everything."""
        state.reset()
        _session["word_offset"] = 0
        _session["utterances"] = []
        _components["input"].value = ""
        _components["conversation"].render([])
        _components["chart"].clear()
        _components["highlight"].clear()
        _components["sparkline"].clear()
        _components["review"].hide()
        _components["status"].update()

    # ── Page definition ───────────────────────────────────────────────

    @ui.page("/")
    def main_page():
        ui.add_head_html(f"<style>{GLOBAL_CSS}</style>")
        # Prevent bare Enter from inserting a newline in textareas;
        # Shift+Enter still inserts a newline normally.
        ui.add_head_html("""<script>
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey &&
                e.target && e.target.tagName === 'TEXTAREA') {
                e.preventDefault();
            }
        });
        </script>""")

        with ui.column().classes("w-full px-6 py-4 gap-4").style(
            "height: 100vh; max-height: 100vh;"
        ):
            # ── Header ──
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("PII Masking").classes("apple-heading")
                _components["sparkline"] = SessionSparkline()
                ui.button("Clear", on_click=on_clear).classes("apple-btn-secondary")

            ui.element("hr").classes("apple-separator").style("width: 100%;")

            # ── Two-column layout: chart left, conversation right ──
            with ui.row().classes("w-full gap-6").style(
                "flex: 1 1 0; min-height: 0;"
            ):
                # ── LEFT: Risk Analysis (50%) ──
                with ui.column().classes("gap-3").style(
                    "flex: 1 1 0; min-width: 0;"
                ):
                    ui.label("Risk Analysis").classes("apple-section-label")
                    _components["chart"] = RiskChart()

                    _components["highlight"] = TextHighlightOverlay()

                    _components["status"] = StatusIndicator()

                # ── RIGHT: Conversation + Input (50%) ──
                with ui.column().classes("gap-3").style(
                    "flex: 1 1 0; min-width: 0; height: 90%;"
                ):
                    # Conversation scrolls to fill space
                    _components["conversation"] = ConversationPanel()

                    # ── Review Panel (hidden by default) ──
                    _components["review"] = ReviewPanel(
                        on_send=on_review_send, on_edit=on_review_edit
                    )

                    # ── Input Area (pinned to bottom, never pushed down) ──
                    with ui.column().classes("w-full gap-2").style(
                        "flex-shrink: 0; margin-top: auto;"
                    ):
                        with ui.row().classes("w-full items-center gap-2"):
                            _components["input"] = ui.textarea(
                                placeholder="Type your message here...",
                                on_change=on_user_type,
                            ).props("outlined autogrow").classes("flex-grow").style(
                                f"font-family: {FONT_STACK};"
                            )
                            # Enter submits; Shift+Enter inserts newline.
                            # Client-side JS prevents the default Enter behavior,
                            # then the server-side handler triggers send.
                            _components["input"].on(
                                "keydown.enter",
                                lambda e: on_enter_key(e),
                                ["shiftKey"],
                                throttle=0.3,
                            )

                            ui.button(
                                icon="send",
                                on_click=on_send_click,
                            ).classes("apple-btn-primary").style(
                                "min-width: 40px; width: 40px; height: 40px; padding: 0; "
                                "border-radius: 12px !important;"
                            ).props("dense flat")

            # ── Timer ──
            ui.timer(0.5, callback=on_timer_tick)
