"""UI components for NiceGUI PII masking client (Apple Design)."""

from __future__ import annotations

import html as html_lib
from typing import Callable, Optional

from nicegui import ui

from ccpp.nicegui.styles import COLORS, FONT_STACK


# ---------------------------------------------------------------------------
# ConversationPanel — iMessage-style scrollable chat history
# ---------------------------------------------------------------------------

class ConversationPanel:
    """Scrollable conversation history with iMessage-style bubbles."""

    def __init__(self) -> None:
        self.scroll = ui.scroll_area().classes("w-full").style(
            "flex: 1 1 auto; min-height: 200px;"
        )
        with self.scroll:
            self.container = ui.column().classes("w-full gap-3 p-2")
        self._placeholder = None
        with self.container:
            self._placeholder = ui.label("Conversation history will appear here...").style(
                f"color: {COLORS['text_tertiary']}; font-size: 14px; padding: 24px 0;"
            )

    def render(self, conversation: list[dict]) -> None:
        """Rebuild the conversation from scratch."""
        self.container.clear()

        if not conversation:
            with self.container:
                ui.label("Conversation history will appear here...").style(
                    f"color: {COLORS['text_tertiary']}; font-size: 14px; padding: 24px 0;"
                )
            return

        for i, msg in enumerate(conversation):
            is_last = i == len(conversation) - 1
            role = msg["role"]
            content = msg["content"]
            metadata = msg.get("metadata")

            with self.container:
                if role == "user":
                    self._render_user_bubble(content, metadata, is_last)
                else:
                    self._render_assistant_bubble(content, is_last)

        # Auto-scroll to bottom
        self.scroll.scroll_to(percent=1.0)

    def append_assistant_bubble(self) -> ui.markdown:
        """Add an empty assistant bubble for streaming and return the markdown element."""
        with self.container:
            md = self._render_assistant_bubble("", is_last=True)
        self.scroll.scroll_to(percent=1.0)
        return md

    def _render_user_bubble(
        self, content: str, metadata: Optional[dict], is_last: bool
    ) -> None:
        classes = "w-full flex justify-end"
        if is_last:
            classes += " fade-in"

        with ui.row().classes(classes):
            with ui.column().classes("items-end gap-1").style("max-width: 75%;"):
                # Bubble
                with ui.element("div").style(
                    f"background: {COLORS['bubble_user']}; "
                    f"color: {COLORS['bubble_user_text']}; "
                    "border-radius: 18px 18px 4px 18px; "
                    "padding: 10px 16px; "
                    "font-size: 15px; line-height: 1.45; "
                    "word-break: break-word;"
                ):
                    was_masked = metadata and metadata.get("was_masked", False)
                    original_text = metadata.get("original_text", content) if metadata else content

                    if was_masked:
                        # Show masked text by default, toggle to original
                        text_label = ui.label(content).style("white-space: pre-wrap;")
                        showing_masked = {"value": True}

                        def toggle_text(tl=text_label, ot=original_text, mc=content, sm=showing_masked):
                            sm["value"] = not sm["value"]
                            tl.text = mc if sm["value"] else ot

                        with ui.row().classes("items-center gap-1 mt-1").style("opacity: 0.7;"):
                            ui.icon("edit", size="12px").style("color: rgba(255,255,255,0.7);")
                            ui.label("Modified").style(
                                "font-size: 11px; color: rgba(255,255,255,0.7); "
                                "cursor: pointer;"
                            ).on("click", toggle_text)
                    else:
                        ui.label(content).style("white-space: pre-wrap;")

                # Expandable details
                if metadata and metadata.get("risk_history"):
                    self._render_details(metadata)

    def _render_assistant_bubble(self, content: str, is_last: bool) -> ui.markdown:
        classes = "w-full flex justify-start"
        if is_last:
            classes += " fade-in"

        md = None
        with ui.row().classes(classes):
            with ui.element("div").style(
                f"background: {COLORS['bubble_assistant']}; "
                f"color: {COLORS['bubble_assistant_text']}; "
                "border-radius: 18px 18px 18px 4px; "
                "padding: 10px 16px; max-width: 75%; "
                "font-size: 15px; line-height: 1.45; "
                "word-break: break-word;"
            ):
                md = ui.markdown(content).classes("assistant-md")
        return md

    def _render_details(self, metadata: dict) -> None:
        risk_history = metadata.get("risk_history", [])
        was_masked = metadata.get("was_masked", False)
        peak_risk = max((r["p_risk"] for r in risk_history), default=0)
        final_ema = risk_history[-1]["ema"] if risk_history else 0

        status_color = COLORS["risk_danger"] if was_masked else COLORS["risk_safe"]
        status_text = "Masked" if was_masked else "Safe"

        with ui.expansion(f"{status_text} — Peak {peak_risk:.2f} · EMA {final_ema:.2f}").classes(
            "w-full"
        ).style("max-width: 75%;"):
            with ui.column().classes("gap-1").style("font-size: 12px;"):
                with ui.row().classes("gap-4"):
                    ui.label(f"Status: {status_text}").style(f"color: {status_color};")
                    ui.label(f"Peak risk: {peak_risk:.3f}").style(
                        f"color: {COLORS['text_secondary']};"
                    )
                    ui.label(f"EMA: {final_ema:.3f}").style(
                        f"color: {COLORS['text_secondary']};"
                    )

                if was_masked:
                    original = metadata.get("original_text", "")
                    masked = metadata.get("masked_text", "")
                    with ui.column().classes("gap-1 mt-2"):
                        ui.label("Original:").style(
                            f"color: {COLORS['text_secondary']}; font-weight: 600;"
                        )
                        ui.label(original).style(
                            f"color: {COLORS['text_secondary']}; "
                            "white-space: pre-wrap; font-size: 12px;"
                        )
                        ui.label("Masked:").style(
                            f"color: {COLORS['text_secondary']}; font-weight: 600;"
                        )
                        ui.label(masked).style(
                            "white-space: pre-wrap; font-size: 12px;"
                        )


# ---------------------------------------------------------------------------
# RiskChart — ECharts line chart for P(RISK) scatter + EMA line
# ---------------------------------------------------------------------------

class RiskChart:
    """Real-time risk visualization using Apache ECharts."""

    def __init__(self) -> None:
        self.chart = ui.echart(self._empty_options()).classes("w-full").style(
            f"height: 340px; border: 1px solid {COLORS['border']}; border-radius: 12px; "
            f"background: {COLORS['bg_primary']};"
        )

    def update(self, risk_history: list[dict], t_high: float = 0.4, t_low: float = 0.2, risk_threshold: float = 0.7) -> None:
        if not risk_history:
            self.clear()
            return

        # Each data point: [char_idx, score, buffer_text]
        # The buffer field contains the text that was classified at that point.
        risk_data = [
            [r["char_idx"], r["p_risk"], r.get("buffer", "")]
            for r in risk_history
        ]
        ema_data = [
            [r["char_idx"], r["ema"], r.get("buffer", "")]
            for r in risk_history
        ]
        current_ema = risk_history[-1]["ema"]
        ema_color = COLORS["chart_ema_high"] if current_ema >= t_high else COLORS["chart_ema_safe"]

        self.chart.options["series"] = [
            # P(RISK) scatter
            {
                "name": "P(Risk)",
                "type": "scatter",
                "data": risk_data,
                "symbolSize": 7,
                "itemStyle": {"color": COLORS["chart_risk_dot"], "opacity": 0.6},
                "z": 2,
            },
            # EMA line
            {
                "name": "EMA",
                "type": "line",
                "data": ema_data,
                "smooth": True,
                "showSymbol": False,
                "lineStyle": {"width": 2.5, "color": ema_color},
                "areaStyle": {"color": ema_color, "opacity": 0.06},
                "z": 3,
                "markLine": {
                    "silent": True,
                    "symbol": "none",
                    "lineStyle": {"type": "dashed", "width": 1},
                    "label": {"fontSize": 10, "fontFamily": FONT_STACK},
                    "data": [
                        {
                            "yAxis": t_high,
                            "label": {
                                "formatter": "T_high",
                                "color": COLORS["chart_threshold_high"],
                            },
                            "lineStyle": {"color": COLORS["chart_threshold_high"]},
                        },
                        {
                            "yAxis": t_low,
                            "label": {
                                "formatter": "T_low",
                                "color": COLORS["chart_threshold_low"],
                            },
                            "lineStyle": {"color": COLORS["chart_threshold_low"]},
                        },
                        {
                            "yAxis": risk_threshold,
                            "label": {
                                "formatter": "Risk",
                                "color": COLORS["risk_danger"],
                            },
                            "lineStyle": {"color": COLORS["risk_danger"], "type": "dashed", "width": 1},
                        },
                    ],
                },
            },
        ]

        self.chart.update()

    def clear(self) -> None:
        self.chart.options.clear()
        self.chart.options.update(self._empty_options())
        self.chart.update()

    @staticmethod
    def _empty_options() -> dict:
        return {
            "animation": True,
            "animationDuration": 300,
            "animationEasing": "cubicOut",
            "grid": {
                "top": 36,
                "right": 24,
                "bottom": 36,
                "left": 48,
                "containLabel": False,
            },
            "xAxis": {
                "type": "value",
                "name": "Word",
                "nameTextStyle": {
                    "color": COLORS["text_secondary"],
                    "fontFamily": FONT_STACK,
                    "fontSize": 11,
                },
                "axisLine": {"lineStyle": {"color": COLORS["border"]}},
                "axisLabel": {"color": COLORS["text_secondary"], "fontSize": 10},
                "splitLine": {"show": False},
                "minInterval": 1,
            },
            "yAxis": {
                "type": "value",
                "min": 0,
                "max": 1,
                "name": "Score",
                "nameTextStyle": {
                    "color": COLORS["text_secondary"],
                    "fontFamily": FONT_STACK,
                    "fontSize": 11,
                },
                "axisLine": {"lineStyle": {"color": COLORS["border"]}},
                "axisLabel": {"color": COLORS["text_secondary"], "fontSize": 10},
                "splitLine": {
                    "lineStyle": {"color": COLORS["chart_grid"], "type": "dashed"}
                },
            },
            "tooltip": {
                "trigger": "item",
                "backgroundColor": "rgba(255,255,255,0.96)",
                "borderColor": COLORS["border"],
                "borderWidth": 1,
                "textStyle": {
                    "color": COLORS["text_primary"],
                    "fontFamily": FONT_STACK,
                    "fontSize": 12,
                },
                "extraCssText": (
                    "border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); "
                    "max-width: 400px; white-space: pre-wrap;"
                ),
                # :formatter is evaluated as JS by NiceGUI's convertDynamicProperties
                ":formatter": """(params) => {
                    const d = params.data || [];
                    const score = (d[1] !== undefined) ? d[1].toFixed(3) : '—';
                    const buf = d[2] || '';
                    const name = params.seriesName || '';
                    let label = '<b>' + name + ':</b> ' + score;
                    if (buf) {
                        const truncated = buf.length > 120 ? '…' + buf.slice(-120) : buf;
                        label += '<br/><span style="color:#86868B;font-size:11px">Buffer: '
                            + truncated.replace(/</g, '&lt;') + '</span>';
                    }
                    return label;
                }""",
            },
            "legend": {
                "show": True,
                "top": 4,
                "right": 16,
                "textStyle": {
                    "color": COLORS["text_secondary"],
                    "fontFamily": FONT_STACK,
                    "fontSize": 11,
                },
                "itemWidth": 12,
                "itemHeight": 8,
            },
            "series": [],
        }


# ---------------------------------------------------------------------------
# SessionSparkline — tiny trend line in the header
# ---------------------------------------------------------------------------

class SessionSparkline:
    """Apple Health-style mini sparkline showing session risk trend."""

    def __init__(self) -> None:
        self._data: list[list[float]] = []  # [[index, ema], ...]
        self.chart = ui.echart(self._options()).style(
            "height: 36px; width: 140px;"
        )

    def add_point(self, peak_risk: float, ema: float) -> None:
        idx = len(self._data)
        self._data.append([idx, ema])
        color = COLORS["chart_ema_high"] if ema >= 0.4 else COLORS["chart_ema_safe"]

        self.chart.options["series"] = [
            {
                "type": "line",
                "data": self._data,
                "smooth": True,
                "showSymbol": False,
                "lineStyle": {"width": 2, "color": color},
                "areaStyle": {"color": color, "opacity": 0.08},
            }
        ]
        self.chart.options["xAxis"]["max"] = max(idx + 2, 5)
        self.chart.update()

    def clear(self) -> None:
        self._data = []
        self.chart.options.clear()
        self.chart.options.update(self._options())
        self.chart.update()

    def _options(self) -> dict:
        return {
            "animation": True,
            "animationDuration": 300,
            "grid": {"top": 4, "right": 4, "bottom": 4, "left": 4},
            "xAxis": {
                "type": "value",
                "show": False,
                "min": 0,
                "max": 5,
            },
            "yAxis": {
                "type": "value",
                "show": False,
                "min": 0,
                "max": 1,
            },
            "tooltip": {"show": False},
            "series": [],
        }


# ---------------------------------------------------------------------------
# ReviewPanel — pre-send review with per-entity approve/reject
# ---------------------------------------------------------------------------

class ReviewPanel:
    """Compact review panel for detected entities before sending to LLM."""

    def __init__(self, on_send: Callable, on_edit: Callable) -> None:
        self._on_send = on_send
        self._on_edit = on_edit
        self._entity_states: dict[int, bool] = {}
        self._original_text = ""
        self._spans: list = []
        self._masked_preview_label: Optional[ui.label] = None

        self.panel = ui.column().classes("w-full").style(
            f"border: 1px solid {COLORS['border']}; border-radius: 10px; "
            f"background: {COLORS['bg_secondary']}; padding: 12px 16px; gap: 8px;"
        )
        self.panel.visible = False

    def show(self, original_text: str, masked_text: str, spans: list) -> None:
        self._original_text = original_text
        self._spans = spans
        self._entity_states = {i: True for i in range(len(spans))}

        self.panel.clear()
        self.panel.visible = True

        with self.panel:
            # Entity pills + buttons in a compact row
            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                ui.label("Detected:").style(
                    f"font-size: 12px; font-weight: 600; color: {COLORS['text_secondary']};"
                )
                for i, span in enumerate(spans):
                    self._render_entity_pill(i, span)

                # Spacer
                ui.element("div").style("flex: 1;")

                ui.button("Edit", on_click=self._on_edit_click).classes(
                    "apple-btn-secondary"
                ).props("dense no-caps unelevated").style(
                    "padding: 0 16px; font-size: 13px; height: 32px; line-height: 32px;"
                )
                ui.button("Send masked", on_click=self._on_send_click).classes(
                    "apple-btn-primary"
                ).props("dense no-caps unelevated").style(
                    "padding: 0 16px; font-size: 13px; height: 32px; line-height: 32px;"
                )

            # Masked preview (single line)
            self._masked_preview_label = ui.label(masked_text).style(
                f"font-size: 12px; color: {COLORS['text_secondary']}; "
                "white-space: pre-wrap; line-height: 1.4;"
            )

    def hide(self) -> None:
        self.panel.visible = False

    def get_approved_spans(self) -> list:
        return [
            span for i, span in enumerate(self._spans) if self._entity_states.get(i, True)
        ]

    def _render_entity_pill(self, index: int, span) -> None:
        entity_text = span.entity_text if hasattr(span, "entity_text") else str(span.get("entity_text", ""))
        category = span.category.value if hasattr(span, "category") else str(span.get("category", ""))

        pill = ui.element("div").classes("entity-pill")
        with pill:
            ui.label(f'"{entity_text}"').style("font-size: 12px;")
            ui.label(category).classes("category")
            switch = ui.switch(value=True).props("dense").style("margin-left: 4px;")

            def on_toggle(e, idx=index, p=pill):
                self._entity_states[idx] = e.value
                if e.value:
                    p.classes(remove="rejected")
                else:
                    p.classes(add="rejected")
                self._update_masked_preview()

            switch.on("update:model-value", on_toggle)

    def _update_masked_preview(self) -> None:
        text = self._original_text
        for span in self.get_approved_spans():
            entity_text = span.entity_text if hasattr(span, "entity_text") else str(span.get("entity_text", ""))
            cat = span.category.value if hasattr(span, "category") else str(span.get("category", ""))
            text = text.replace(entity_text, f"[{cat.upper()}]")
        if self._masked_preview_label:
            self._masked_preview_label.text = text

    async def _on_send_click(self) -> None:
        await self._on_send(self.get_approved_spans())

    def _on_edit_click(self) -> None:
        self.hide()
        self._on_edit()


# ---------------------------------------------------------------------------
# TextHighlightOverlay — colored underlines beneath the textarea
# ---------------------------------------------------------------------------

class TextHighlightOverlay:
    """Persistent utterance log with colored risk underlines.

    Shows all past utterances (grayed, with risk colors) plus the current
    in-progress buffer on a new line.
    """

    def __init__(self) -> None:
        self.container = ui.html("").style(
            f"font-size: 13px; line-height: 1.7; padding: 8px 0; min-height: 20px; "
            f"font-family: {FONT_STACK}; word-break: break-word;"
        )

    def render_all(
        self,
        past_utterances: list[dict],
        current_text: str,
        current_risk_history: list[dict],
    ) -> None:
        """Render all past utterances plus the current in-progress buffer.

        Args:
            past_utterances: list of {"text", "risk_history", "was_masked"} dicts
            current_text: current buffer being typed
            current_risk_history: risk entries for the current buffer (local word indices)
        """
        parts: list[str] = []

        # Past utterances (dimmed)
        for utt in past_utterances:
            line = self._render_utterance(
                utt["text"], utt["risk_history"], dimmed=True,
            )
            parts.append(line)

        # Current buffer (bright)
        if current_text:
            line = self._render_utterance(
                current_text, current_risk_history, dimmed=False,
            )
            parts.append(line)

        self.container.content = "<br/>".join(parts) if parts else ""

    def _render_utterance(
        self, text: str, risk_history: list[dict], dimmed: bool,
    ) -> str:
        """Render one utterance with colored underlines."""
        # Build word_index -> score map. risk_history entries have "char_idx"
        # which may be a global word index; we need local word index.
        # Compute the local index by finding the min char_idx in this history.
        if risk_history:
            min_idx = min(r["char_idx"] for r in risk_history)
        else:
            min_idx = 0

        word_scores: dict[int, float] = {}
        for entry in risk_history:
            local_word_idx = entry["char_idx"] - min_idx
            word_scores[local_word_idx] = entry["p_risk"]

        words = text.split(" ")
        word_parts: list[str] = []
        opacity = "0.5" if dimmed else "1.0"

        for wi, word in enumerate(words):
            escaped = html_lib.escape(word)
            score = word_scores.get(wi)

            if score is not None:
                if score >= 0.7:
                    color = COLORS["risk_danger"]
                    border = f"border-bottom: 2px solid {color};"
                elif score >= 0.3:
                    color = COLORS["risk_warning"]
                    border = f"border-bottom: 2px solid {color};"
                else:
                    color = COLORS["risk_safe"]
                    border = f"border-bottom: 1px solid {color};"
                word_parts.append(
                    f'<span style="{border} opacity: {opacity};">{escaped}</span>'
                )
            else:
                word_parts.append(
                    f'<span style="opacity: {opacity};">{escaped}</span>'
                )

        return " ".join(word_parts)

    def clear(self) -> None:
        self.container.content = ""


# ---------------------------------------------------------------------------
# StatusIndicator — minimal colored dot + label
# ---------------------------------------------------------------------------

class StatusIndicator:
    """Apple-style minimal status indicator with colored dot."""

    def __init__(self) -> None:
        with ui.row().classes("items-center gap-2"):
            self._dot = ui.html(self._dot_html(COLORS["risk_safe"]))
            self._label = ui.label("Ready").style(
                f"font-size: 12px; color: {COLORS['text_secondary']};"
            )

    def update(
        self,
        is_processing: bool = False,
        is_classifying: bool = False,
        chars_processed: int = 0,
        was_masked: bool = False,
        error: Optional[str] = None,
        send_blocked: bool = False,
    ) -> None:
        if send_blocked:
            self._dot.content = self._dot_html(COLORS["risk_warning"])
            self._label.text = "Analyzing — send when ready"
        elif error:
            self._dot.content = self._dot_html(COLORS["risk_danger"])
            self._label.text = f"Error: {error}"
        elif is_processing:
            self._dot.content = self._dot_html(COLORS["risk_warning"])
            self._label.text = "Processing..."
        elif is_classifying:
            self._dot.content = self._dot_html(COLORS["risk_warning"])
            self._label.text = "Analyzing..."
        elif chars_processed > 0:
            color = COLORS["risk_danger"] if was_masked else COLORS["risk_safe"]
            self._dot.content = self._dot_html(color)
            label = f"{chars_processed} chars"
            if was_masked:
                label += " (masked)"
            self._label.text = label
        else:
            self._dot.content = self._dot_html(COLORS["risk_safe"])
            self._label.text = "Ready"

    @staticmethod
    def _dot_html(color: str) -> str:
        return (
            f'<div style="width: 8px; height: 8px; border-radius: 50%; '
            f'background: {color}; flex-shrink: 0;"></div>'
        )
