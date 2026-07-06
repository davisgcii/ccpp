"""Design system — an instrument-panel identity for the PII masking demo.

Slate-biased neutrals (chosen, not default grey), one signal accent, and risk
semantics (safe/warn/danger) kept separate from the accent. System sans for
chrome, a monospace face for all data (scores, tokens, thresholds, chips).
"""

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
)
FONT_MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"

# Palette (light theme values). Used for inline styles and the ECharts config.
COLORS = {
    "paper": "#FCFCFB",
    "surface": "#FFFFFF",
    "surface_2": "#F4F5F7",
    "surface_3": "#EDEFF3",
    "ink": "#14171F",
    "ink_2": "#565B66",
    "ink_3": "#8A909C",
    "line": "#E6E8EC",
    "line_strong": "#D7DAE0",
    "accent": "#2F6BFF",
    "accent_weak": "#EAF0FF",
    "accent_ink": "#1B49C9",
    "safe": "#12B76A",
    "warn": "#F79009",
    "danger": "#F04438",
    "redact": "#14171F",
    "redact_ink": "#FCFCFB",
    "grid": "#E6E8EC",
    # Legacy aliases (kept so any un-migrated inline styles still resolve).
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F4F5F7",
    "bg_tertiary": "#FCFCFB",
    "text_primary": "#14171F",
    "text_secondary": "#565B66",
    "text_tertiary": "#8A909C",
    "border": "#E6E8EC",
    "border_focus": "#2F6BFF",
    "bubble_user": "#2F6BFF",
    "bubble_user_text": "#FFFFFF",
    "bubble_assistant": "#F4F5F7",
    "bubble_assistant_text": "#14171F",
    "risk_safe": "#12B76A",
    "risk_warning": "#F79009",
    "risk_danger": "#F04438",
    "chart_risk_dot": "#2F6BFF",
    "chart_ema_safe": "#2F6BFF",
    "chart_ema_high": "#2F6BFF",
    "chart_threshold_high": "#F79009",
    "chart_threshold_low": "#8A909C",
    "chart_grid": "#E6E8EC",
    "accent_light": "#EAF0FF",
}

GLOBAL_CSS = f"""
:root {{
  --paper:#FCFCFB; --surface:#FFFFFF; --surface-2:#F4F5F7; --surface-3:#EDEFF3;
  --ink:#14171F; --ink-2:#565B66; --ink-3:#8A909C;
  --line:#E6E8EC; --line-strong:#D7DAE0;
  --accent:#2F6BFF; --accent-weak:#EAF0FF; --accent-ink:#1B49C9;
  --safe:#12B76A; --warn:#F79009; --danger:#F04438;
  --redact:#14171F; --redact-ink:#FCFCFB;
  --shadow:0 1px 2px rgba(20,23,31,.04), 0 8px 24px -12px rgba(20,23,31,.12);
  --shadow-sm:0 1px 2px rgba(20,23,31,.05);
  --font-sans:{FONT_STACK};
  --font-mono:{FONT_MONO};
}}

body, .nicegui-content, .q-page {{
  background:var(--paper) !important;
  font-family:var(--font-sans) !important;
  color:var(--ink);
  -webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;
}}
.q-page {{ max-width:100%; padding:0; }}
.nicegui-content {{ padding:0; }}

/* ── Top bar ── */
.brand-glyph {{ width:30px; height:30px; border-radius:9px; background:var(--redact);
  position:relative; flex:0 0 auto; }}
.brand-glyph::before {{ content:""; position:absolute; left:6px; right:6px; top:13px;
  height:4px; border-radius:2px; background:var(--redact-ink); }}
.brand-title {{ font-size:18px; font-weight:650; letter-spacing:-.01em; color:var(--ink); }}
.brand-sub {{ font:500 11px/1 var(--font-mono); color:var(--ink-3); letter-spacing:.02em; margin-top:3px; }}
.live-pill {{ display:inline-flex; align-items:center; gap:7px; font:600 11px/1 var(--font-mono);
  color:var(--safe); background:color-mix(in srgb,var(--safe) 12%,transparent);
  padding:7px 11px; border-radius:999px; letter-spacing:.04em; text-transform:uppercase; }}
.live-pill .dot {{ width:7px; height:7px; border-radius:50%; background:var(--safe);
  animation:pulse 2s infinite; }}
@keyframes pulse {{ 0%{{box-shadow:0 0 0 0 color-mix(in srgb,var(--safe) 60%,transparent);}}
  70%{{box-shadow:0 0 0 6px transparent;}} 100%{{box-shadow:0 0 0 0 transparent;}} }}

/* ── Cards ── */
.panel {{ background:var(--surface); border:1px solid var(--line); border-radius:16px;
  box-shadow:var(--shadow); }}
.eyebrow {{ font:600 11px/1 var(--font-mono); letter-spacing:.09em; text-transform:uppercase;
  color:var(--ink-3); }}

/* ── Stat row ── */
.stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--line);
  border-radius:12px; overflow:hidden; border:1px solid var(--line); }}
.stat {{ background:var(--surface); padding:12px 14px; }}
.stat .k {{ font:600 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3); }}
.stat .v {{ font:600 22px/1.1 var(--font-mono); font-variant-numeric:tabular-nums; margin-top:7px; letter-spacing:-.01em; color:var(--ink); }}
.stat .v.warn {{ color:var(--warn); }} .stat .v.danger {{ color:var(--danger); }} .stat .v.accent {{ color:var(--accent); }}
.stat .v small {{ font-size:12px; color:var(--ink-3); font-weight:500; }}

/* ── Chart legend ── */
.legend {{ display:flex; gap:16px; flex-wrap:wrap; }}
.legend span {{ display:inline-flex; align-items:center; gap:6px; font:500 11px/1 var(--font-mono); color:var(--ink-2); }}
.legend i {{ width:14px; height:0; border-top:2px solid; border-radius:2px; }}
.legend i.dot {{ width:8px; height:8px; border-radius:50%; border:0; }}
.legend i.dash {{ border-top-style:dashed; }}

/* ── Token meter ── */
.meter-lbl {{ font:600 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3); }}
.toks {{ font:500 15px/2.1 var(--font-sans); color:var(--ink); }}
.tok {{ padding:2px 1px; border-bottom:2px solid transparent; }}
.tok.s0 {{ color:var(--ink-3); }}
.tok.s1 {{ border-color:color-mix(in srgb,var(--safe) 70%,transparent); }}
.tok.s2 {{ border-color:var(--warn); }}
.tok.s3 {{ border-color:var(--danger); color:var(--ink); font-weight:600; }}

/* ── Conversation ── */
.msg {{ max-width:82%; }}
.msg.user {{ align-self:flex-end; }}
.msg.bot {{ align-self:flex-start; }}
.bubble {{ padding:10px 14px; border-radius:16px; font-size:14.5px; }}
.msg.user .bubble {{ background:var(--accent); color:#fff; border-bottom-right-radius:6px; }}
.msg.bot .bubble {{ background:var(--surface-2); color:var(--ink); border-bottom-left-radius:6px; }}
.msg-meta {{ display:flex; align-items:center; gap:8px; justify-content:flex-end; margin-top:6px;
  font:500 11px/1 var(--font-mono); color:var(--ink-3); }}
.tag {{ display:inline-flex; align-items:center; gap:5px; padding:3px 7px; border-radius:6px;
  font:600 10px/1 var(--font-mono); letter-spacing:.03em; }}
.tag.masked {{ background:color-mix(in srgb,var(--danger) 13%,transparent); color:var(--danger); }}
.tag.safe {{ background:color-mix(in srgb,var(--safe) 13%,transparent); color:var(--safe); }}
.redact {{ display:inline-flex; align-items:center; gap:6px; background:var(--redact); color:var(--redact-ink);
  padding:2px 8px; border-radius:6px; font:600 12px/1.4 var(--font-mono); letter-spacing:.03em; }}
.redact::before {{ content:""; width:6px; height:6px; border-radius:1px; background:var(--redact-ink); opacity:.55; }}

/* ── Review panel ── */
.review {{ border:1px solid var(--line-strong); border-radius:14px; background:var(--surface-2); padding:13px 15px; }}
.review .rhd {{ font:600 10px/1 var(--font-mono); letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3); }}
.ent {{ display:flex; align-items:center; gap:10px; padding:9px 11px; background:var(--surface);
  border:1px solid var(--line); border-radius:10px; }}
.ent .val {{ font:600 13px/1 var(--font-mono); color:var(--ink); flex:1; min-width:0;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.ent .cat {{ font:600 10px/1 var(--font-mono); letter-spacing:.03em; color:var(--danger);
  background:color-mix(in srgb,var(--danger) 12%,transparent); padding:4px 7px; border-radius:5px; }}

/* ── Buttons ── */
.btn-line {{ font:500 13px/1 var(--font-sans); padding:9px 15px; border-radius:9px;
  border:1px solid var(--line-strong); background:var(--surface); color:var(--ink-2); }}
.btn-line:hover {{ background:var(--surface-2); color:var(--ink); }}
.apple-btn-primary {{ background:var(--accent) !important; color:#fff !important; border-radius:12px !important;
  font-weight:600 !important; font-size:13px !important; text-transform:none !important; letter-spacing:0 !important;
  box-shadow:var(--shadow-sm) !important; }}
.apple-btn-primary:hover {{ background:var(--accent-ink) !important; }}
.apple-btn-secondary {{ color:var(--ink-2) !important; background:var(--surface) !important;
  border:1px solid var(--line-strong) !important; border-radius:9px !important; font-weight:500 !important;
  font-size:13px !important; text-transform:none !important; letter-spacing:0 !important; box-shadow:none !important; }}
.apple-btn-secondary:hover {{ background:var(--surface-2) !important; color:var(--ink) !important; }}

/* ── Input ── */
.q-field--outlined .q-field__control {{ border-radius:13px !important; background:var(--surface-2) !important; }}
.q-field--outlined .q-field__control:before {{ border-color:var(--line) !important; }}
.q-field--outlined.q-field--focused .q-field__control:before {{ border-color:var(--accent) !important; border-width:2px !important; }}
.q-field__native, .q-field__input {{ font-family:var(--font-sans) !important; font-size:14.5px !important;
  color:var(--ink) !important; line-height:1.5 !important; }}
.q-field__label {{ font-family:var(--font-sans) !important; color:var(--ink-3) !important; }}

/* ── Scrollbars ── */
::-webkit-scrollbar {{ width:7px; height:7px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:var(--line-strong); border-radius:4px; }}
::-webkit-scrollbar-thumb:hover {{ background:var(--ink-3); }}

/* ── Markdown in assistant bubbles ── */
.assistant-md p {{ margin:0 0 .4em 0; }}
.assistant-md p:last-child {{ margin-bottom:0; }}
.assistant-md ul, .assistant-md ol {{ margin:.2em 0; padding-left:1.4em; }}
.assistant-md pre {{ margin:.4em 0; padding:8px; border-radius:8px; background:rgba(0,0,0,.04); font-size:13px; }}
.assistant-md code {{ font-family:var(--font-mono); font-size:13px; }}

/* ── Misc ── */
.apple-separator {{ background:var(--line); height:1px; border:none; margin:0; }}
@keyframes fadeIn {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:translateY(0); }} }}
.fade-in {{ animation:fadeIn .3s ease-out; }}
"""
