"""UI components for the NiceGUI PII masking client (instrument-panel design)."""

from __future__ import annotations

import html as html_lib
import re
from typing import Callable, Optional

from nicegui import ui

from ccpp.types import MaskingConfig
from ccpp.nicegui.styles import COLORS, FONT_MONO

# Matches masked placeholders like [CONTACT] / [GOV_ID] so they can be rendered
# as redaction chips inside a bubble.
_MASK_TOKEN = re.compile(r"\[([A-Z][A-Z_]*)\]")


def _redacted_html(text: str) -> str:
    """Escape text and render [CATEGORY] placeholders as redaction chips."""
    out: list[str] = []
    pos = 0
    for m in _MASK_TOKEN.finditer(text):
        out.append(html_lib.escape(text[pos:m.start()]))
        out.append(f'<span class="redact">{html_lib.escape(m.group(1))}</span>')
        pos = m.end()
    out.append(html_lib.escape(text[pos:]))
    return "".join(out)


# ---------------------------------------------------------------------------
# StatRow — summary tiles above the chart (current P(risk), EMA, masked count)
# ---------------------------------------------------------------------------

class StatRow:
    """Three summary tiles that surface the current state at a glance."""

    def __init__(self) -> None:
        self.el = ui.html(self._html(0.0, 0.0, 0.4, 0)).classes("w-full")

    def update(self, p_risk: float, ema: float, t_high: float, masked: int) -> None:
        self.el.content = self._html(p_risk, ema, t_high, masked)

    @staticmethod
    def _html(p_risk: float, ema: float, t_high: float, masked: int) -> str:
        risk_cls = "danger" if p_risk >= 0.7 else ("warn" if p_risk >= 0.4 else "")
        ema_cls = "warn" if ema >= t_high else ""
        return f"""
        <div class="stats">
          <div class="stat"><div class="k">Current P(risk)</div>
            <div class="v {risk_cls}">{p_risk:.2f}</div></div>
          <div class="stat"><div class="k">EMA</div>
            <div class="v {ema_cls}">{ema:.2f}<small> / {t_high:.2f} T</small></div></div>
          <div class="stat"><div class="k">Masked</div>
            <div class="v accent">{masked}<small> {'entity' if masked == 1 else 'entities'}</small></div></div>
        </div>"""


# ---------------------------------------------------------------------------
# ConversationPanel — chat history with redaction chips
# ---------------------------------------------------------------------------

class ConversationPanel:
    """Scrollable conversation history."""

    def __init__(self) -> None:
        self.scroll = ui.scroll_area().classes("w-full").style(
            "flex: 1 1 auto; min-height: 200px;"
        )
        with self.scroll:
            self.container = ui.column().classes("w-full gap-3 p-2")
        with self.container:
            self._placeholder()

    def _placeholder(self) -> None:
        ui.label("Conversation will appear here.").style(
            f"color: {COLORS['ink_3']}; font-size: 14px; padding: 24px 4px; "
            f"font-family: {FONT_MONO};"
        )

    def render(self, conversation: list[dict]) -> None:
        self.container.clear()
        if not conversation:
            with self.container:
                self._placeholder()
            return

        for i, msg in enumerate(conversation):
            is_last = i == len(conversation) - 1
            with self.container:
                if msg["role"] == "user":
                    self._render_user_bubble(msg["content"], msg.get("metadata"), is_last)
                else:
                    self._render_assistant_bubble(msg["content"], is_last)
        self.scroll.scroll_to(percent=1.0)

    def append_assistant_bubble(self) -> ui.markdown:
        with self.container:
            md = self._render_assistant_bubble("", is_last=True)
        self.scroll.scroll_to(percent=1.0)
        return md

    def _render_user_bubble(self, content: str, metadata: Optional[dict], is_last: bool) -> None:
        wrap = "msg user" + (" fade-in" if is_last else "")
        was_masked = bool(metadata and metadata.get("was_masked", False))
        with ui.column().classes(wrap).style("align-self: flex-end; align-items: flex-end;"):
            ui.html(f'<div class="bubble">{_redacted_html(content)}</div>')
            if metadata and metadata.get("risk_history"):
                risk_history = metadata["risk_history"]
                peak = max((r["p_risk"] for r in risk_history), default=0)
                ema = risk_history[-1]["ema"] if risk_history else 0
                tag = ('<span class="tag masked">masked</span>' if was_masked
                       else '<span class="tag safe">clear</span>')
                ui.html(
                    f'<div class="msg-meta">{tag}peak {peak:.2f} · ema {ema:.2f}</div>'
                )

    def _render_assistant_bubble(self, content: str, is_last: bool) -> ui.markdown:
        wrap = "msg bot" + (" fade-in" if is_last else "")
        md = None
        with ui.element("div").classes(wrap):
            with ui.element("div").classes("bubble"):
                md = ui.markdown(content).classes("assistant-md")
        return md


# ---------------------------------------------------------------------------
# RiskChart — ECharts EMA trace + P(risk) scatter + threshold references
# ---------------------------------------------------------------------------

class RiskChart:
    """Real-time risk instrument using Apache ECharts."""

    def __init__(self) -> None:
        self.chart = ui.echart(self._empty_options()).classes("w-full").style(
            "height: 260px; background: transparent;"
        )

    def update(self, risk_history: list[dict], t_high: float = 0.4,
               t_low: float = 0.2, risk_threshold: float = 0.7) -> None:
        if not risk_history:
            self.clear()
            return

        risk_data = [[r["char_idx"], r["p_risk"], r.get("buffer", "")] for r in risk_history]
        ema_data = [[r["char_idx"], r["ema"], r.get("buffer", "")] for r in risk_history]
        last = ema_data[-1]
        accent = COLORS["accent"]

        self.chart.options["series"] = [
            {
                "name": "P(risk)",
                "type": "scatter",
                "data": risk_data,
                "symbolSize": 8,
                "itemStyle": {"color": accent, "opacity": 0.55},
                "z": 2,
            },
            {
                "name": "EMA",
                "type": "line",
                "data": ema_data,
                "smooth": True,
                "showSymbol": False,
                "lineStyle": {"width": 2.5, "color": accent},
                "areaStyle": {"color": {
                    "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                    "colorStops": [
                        {"offset": 0, "color": "rgba(47,107,255,0.22)"},
                        {"offset": 1, "color": "rgba(47,107,255,0.0)"},
                    ],
                }},
                "z": 3,
                # Emphasized live endpoint.
                "markPoint": {
                    "symbol": "circle", "symbolSize": 11, "silent": True,
                    "data": [{"coord": [last[0], last[1]]}],
                    "itemStyle": {"color": accent, "borderColor": COLORS["surface"], "borderWidth": 2},
                    "label": {"show": False},
                },
                "markLine": {
                    "silent": True, "symbol": "none",
                    "lineStyle": {"type": "dashed", "width": 1},
                    "label": {"fontSize": 10, "fontFamily": FONT_MONO, "fontWeight": "bold"},
                    "data": [
                        {"yAxis": risk_threshold,
                         "label": {"formatter": f"RISK · {risk_threshold:.2f}", "color": COLORS["danger"]},
                         "lineStyle": {"color": COLORS["danger"]}},
                        {"yAxis": t_high,
                         "label": {"formatter": f"T_high · {t_high:.2f}", "color": COLORS["warn"]},
                         "lineStyle": {"color": COLORS["warn"]}},
                        {"yAxis": t_low,
                         "label": {"formatter": f"T_low · {t_low:.2f}", "color": COLORS["ink_3"]},
                         "lineStyle": {"color": COLORS["ink_3"]}},
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
        axis_label = {"color": COLORS["ink_3"], "fontFamily": FONT_MONO, "fontSize": 10}
        axis_name = {"color": COLORS["ink_3"], "fontFamily": FONT_MONO, "fontSize": 10}
        return {
            "animation": True,
            "animationDuration": 300,
            "animationEasing": "cubicOut",
            "grid": {"top": 30, "right": 18, "bottom": 30, "left": 40, "containLabel": False},
            "xAxis": {
                "type": "value", "name": "word", "nameLocation": "end",
                "nameTextStyle": axis_name,
                "axisLine": {"show": False},
                "axisTick": {"show": False},
                "axisLabel": axis_label,
                "splitLine": {"show": False},
                "minInterval": 1,
            },
            "yAxis": {
                "type": "value", "min": 0, "max": 1,
                "axisLine": {"show": False},
                "axisTick": {"show": False},
                "axisLabel": axis_label,
                "splitLine": {"lineStyle": {"color": COLORS["line"], "type": "solid"}},
            },
            "tooltip": {
                "trigger": "item",
                "backgroundColor": COLORS["surface"],
                "borderColor": COLORS["line"],
                "borderWidth": 1,
                "textStyle": {"color": COLORS["ink"], "fontFamily": FONT_MONO, "fontSize": 12},
                "extraCssText": "border-radius: 10px; box-shadow: 0 6px 20px rgba(20,23,31,0.12); max-width: 360px; white-space: pre-wrap;",
                ":formatter": """(params) => {
                    const d = params.data || [];
                    const score = (d[1] !== undefined) ? d[1].toFixed(3) : '—';
                    const buf = d[2] || '';
                    let label = '<b>' + (params.seriesName || '') + '</b> ' + score;
                    if (buf) {
                        const t = buf.length > 100 ? '…' + buf.slice(-100) : buf;
                        label += '<br/><span style="color:#8A909C;font-size:11px">' + t.replace(/</g, '&lt;') + '</span>';
                    }
                    return label;
                }""",
            },
            "legend": {"show": False},
            "series": [],
        }


# ---------------------------------------------------------------------------
# ReviewPanel — pre-send review with per-entity approve/reject
# ---------------------------------------------------------------------------

class ReviewPanel:
    """Review panel for detected entities before sending to the LLM."""

    def __init__(self, on_send: Callable, on_edit: Callable,
                 masking: Optional[MaskingConfig] = None) -> None:
        self._on_send = on_send
        self._on_edit = on_edit
        self._masking = masking or MaskingConfig()
        self._entity_states: dict[int, bool] = {}
        self._original_text = ""
        self._spans: list = []
        self._preview: Optional[ui.html] = None

        self.panel = ui.column().classes("review w-full").style("gap: 10px;")
        self.panel.visible = False

    def show(self, original_text: str, masked_text: str, spans: list) -> None:
        self._original_text = original_text
        self._spans = spans
        self._entity_states = {i: True for i in range(len(spans))}
        self.panel.clear()
        self.panel.visible = True

        with self.panel:
            ui.html('<div class="rhd">Detected · review before sending</div>')
            for i, span in enumerate(spans):
                self._render_entity(i, span)
            self._preview = ui.html(self._preview_html(masked_text))
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Edit", on_click=self._on_edit_click).classes(
                    "apple-btn-secondary").props("dense no-caps unelevated").style(
                    "padding: 0 16px; height: 34px;")
                ui.button("Send masked", on_click=self._on_send_click).classes(
                    "apple-btn-primary").props("dense no-caps unelevated").style(
                    "padding: 0 16px; height: 34px;")

    def hide(self) -> None:
        self.panel.visible = False

    def get_approved_spans(self) -> list:
        return [s for i, s in enumerate(self._spans) if self._entity_states.get(i, True)]

    def _render_entity(self, index: int, span) -> None:
        entity_text = span.entity_text if hasattr(span, "entity_text") else str(span.get("entity_text", ""))
        category = span.category.value if hasattr(span, "category") else str(span.get("category", ""))
        with ui.row().classes("ent w-full items-center"):
            ui.html(f'<span class="val">"{html_lib.escape(entity_text)}"</span>'
                    f'<span class="cat">{html_lib.escape(category.upper())}</span>')
            switch = ui.switch(value=True).props("dense color=primary")

            def on_toggle(e, idx=index):
                self._entity_states[idx] = e.value
                self._update_preview()

            switch.on("update:model-value", on_toggle)

    def _preview_html(self, text: str) -> str:
        return (f'<div style="font:500 12px/1.5 {FONT_MONO}; color: {COLORS["ink_2"]};'
                f' white-space: pre-wrap;">{_redacted_html(text)}</div>')

    def _update_preview(self) -> None:
        text = self._masking.apply(self._original_text, self.get_approved_spans())
        if self._preview:
            self._preview.content = self._preview_html(text)

    async def _on_send_click(self) -> None:
        await self._on_send(self.get_approved_spans())

    def _on_edit_click(self) -> None:
        self.hide()
        self._on_edit()


# ---------------------------------------------------------------------------
# TextHighlightOverlay — the live token-risk meter
# ---------------------------------------------------------------------------

class TextHighlightOverlay:
    """Per-word risk underlines for past utterances + the current buffer."""

    def __init__(self) -> None:
        self.container = ui.html("").classes("toks").style("min-height: 20px;")

    def render_all(self, past_utterances: list[dict], current_text: str,
                   current_risk_history: list[dict]) -> None:
        parts: list[str] = []
        for utt in past_utterances:
            parts.append(self._render_utterance(utt["text"], utt["risk_history"], dimmed=True))
        if current_text:
            parts.append(self._render_utterance(current_text, current_risk_history, dimmed=False))
        self.container.content = "<br/>".join(parts) if parts else ""

    def _render_utterance(self, text: str, risk_history: list[dict], dimmed: bool) -> str:
        min_idx = min((r["char_idx"] for r in risk_history), default=0)
        word_scores = {r["char_idx"] - min_idx: r["p_risk"] for r in risk_history}
        opacity = "0.45" if dimmed else "1.0"
        parts: list[str] = []
        for wi, word in enumerate(text.split(" ")):
            escaped = html_lib.escape(word)
            score = word_scores.get(wi)
            if score is None:
                cls = "s0"
            elif score >= 0.7:
                cls = "s3"
            elif score >= 0.3:
                cls = "s2"
            else:
                cls = "s1"
            parts.append(f'<span class="tok {cls}" style="opacity:{opacity};">{escaped}</span>')
        return " ".join(parts)

    def clear(self) -> None:
        self.container.content = ""


# ---------------------------------------------------------------------------
# StatusIndicator — minimal state line under the meter
# ---------------------------------------------------------------------------

class StatusIndicator:
    """Minimal status line (mono)."""

    def __init__(self) -> None:
        self.el = ui.html(self._html(COLORS["safe"], "Ready"))

    def update(self, is_processing: bool = False, is_classifying: bool = False,
               chars_processed: int = 0, was_masked: bool = False,
               error: Optional[str] = None, send_blocked: bool = False) -> None:
        if send_blocked:
            self.el.content = self._html(COLORS["warn"], "Analyzing — send when ready")
        elif error:
            self.el.content = self._html(COLORS["danger"], f"Error: {error}")
        elif is_processing:
            self.el.content = self._html(COLORS["warn"], "Processing…")
        elif is_classifying:
            self.el.content = self._html(COLORS["warn"], "Analyzing…")
        elif chars_processed > 0:
            color = COLORS["danger"] if was_masked else COLORS["safe"]
            self.el.content = self._html(color, f"{chars_processed} chars" + (" · masked" if was_masked else " · clear"))
        else:
            self.el.content = self._html(COLORS["safe"], "Ready")

    @staticmethod
    def _html(color: str, text: str) -> str:
        return (f'<div style="display:flex;align-items:center;gap:8px;'
                f'font:500 11px/1 {FONT_MONO};color:{COLORS["ink_3"]};">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{color};'
                f'flex-shrink:0;"></span>{html_lib.escape(text)}</div>')
