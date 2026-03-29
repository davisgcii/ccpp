"""Apple Design System — color tokens, typography, and global CSS."""

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', "
    "'Helvetica Neue', Arial, sans-serif"
)

COLORS = {
    # Backgrounds
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F5F5F7",
    "bg_tertiary": "#FAFAFA",
    # Text
    "text_primary": "#1D1D1F",
    "text_secondary": "#86868B",
    "text_tertiary": "#AEAEB2",
    # Accent
    "accent": "#007AFF",
    "accent_light": "#E8F2FF",
    # Borders
    "border": "#E5E5EA",
    "border_focus": "#007AFF",
    # Conversation bubbles
    "bubble_user": "#007AFF",
    "bubble_user_text": "#FFFFFF",
    "bubble_assistant": "#F0F0F5",
    "bubble_assistant_text": "#1D1D1F",
    # Risk / status
    "risk_safe": "#34C759",
    "risk_warning": "#FF9500",
    "risk_danger": "#FF3B30",
    # Chart
    "chart_risk_dot": "#007AFF",
    "chart_ema_safe": "#34C759",
    "chart_ema_high": "#FF3B30",
    "chart_threshold_high": "#FF9500",
    "chart_threshold_low": "#AEAEB2",
    "chart_grid": "#F5F5F7",
}

GLOBAL_CSS = f"""
/* ── Apple Design Reset ── */

body, .nicegui-content {{
    background-color: {COLORS["bg_primary"]} !important;
    font-family: {FONT_STACK} !important;
    color: {COLORS["text_primary"]};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

/* Let the page use full width */
.q-page {{
    max-width: 100%;
    padding: 0;
}}

/* ── Typography ── */

.apple-heading {{
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.5px;
    color: {COLORS["text_primary"]};
}}

.apple-section-label {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: {COLORS["text_secondary"]};
}}

/* ── Inputs ── */

.q-field--outlined .q-field__control {{
    border-radius: 12px !important;
    border-color: {COLORS["border"]} !important;
    background: {COLORS["bg_primary"]} !important;
}}

.q-field--outlined .q-field__control:before {{
    border-color: {COLORS["border"]} !important;
}}

.q-field--outlined.q-field--focused .q-field__control:before {{
    border-color: {COLORS["border_focus"]} !important;
    border-width: 2px !important;
}}

.q-field__native, .q-field__input {{
    font-family: {FONT_STACK} !important;
    font-size: 15px !important;
    color: {COLORS["text_primary"]} !important;
    line-height: 1.5 !important;
}}

.q-field__label {{
    font-family: {FONT_STACK} !important;
    color: {COLORS["text_secondary"]} !important;
}}

/* ── Buttons ── */

.apple-btn-primary {{
    background-color: {COLORS["accent"]} !important;
    color: white !important;
    border-radius: 980px !important;
    font-weight: 500 !important;
    font-size: 15px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    padding: 8px 20px !important;
    box-shadow: none !important;
}}

.apple-btn-primary:hover {{
    background-color: #0066D6 !important;
}}

.apple-btn-secondary {{
    color: {COLORS["accent"]} !important;
    background: transparent !important;
    border-radius: 980px !important;
    font-weight: 500 !important;
    font-size: 15px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
}}

.apple-btn-secondary:hover {{
    background-color: {COLORS["accent_light"]} !important;
}}

/* ── Cards ── */

.apple-card {{
    border-radius: 12px;
    border: 1px solid {COLORS["border"]};
    background: {COLORS["bg_primary"]};
    box-shadow: none;
}}

/* ── Scrollbars (webkit) ── */

::-webkit-scrollbar {{
    width: 6px;
    height: 6px;
}}

::-webkit-scrollbar-track {{
    background: transparent;
}}

::-webkit-scrollbar-thumb {{
    background: {COLORS["text_tertiary"]};
    border-radius: 3px;
}}

::-webkit-scrollbar-thumb:hover {{
    background: {COLORS["text_secondary"]};
}}

/* ── Markdown inside assistant bubbles ── */

.assistant-md p {{
    margin: 0 0 0.4em 0;
}}
.assistant-md p:last-child {{
    margin-bottom: 0;
}}
.assistant-md ul, .assistant-md ol {{
    margin: 0.2em 0;
    padding-left: 1.4em;
}}
.assistant-md pre {{
    margin: 0.4em 0;
    padding: 8px;
    border-radius: 6px;
    background: rgba(0,0,0,0.04);
    font-size: 13px;
}}
.assistant-md code {{
    font-size: 13px;
}}

/* ── Animations ── */

@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

.fade-in {{
    animation: fadeIn 0.3s ease-out;
}}

@keyframes slideDown {{
    from {{ opacity: 0; max-height: 0; }}
    to   {{ opacity: 1; max-height: 500px; }}
}}

.slide-down {{
    animation: slideDown 0.3s ease-out;
    overflow: hidden;
}}

/* ── Separator ── */

.apple-separator {{
    background: {COLORS["border"]};
    height: 1px;
    border: none;
    margin: 0;
}}

/* ── Expansion panels ── */

.q-expansion-item {{
    border-radius: 8px;
}}

.q-expansion-item .q-item {{
    min-height: 32px !important;
    padding: 4px 8px !important;
}}

.q-expansion-item .q-item__label {{
    font-size: 12px !important;
    color: {COLORS["text_secondary"]} !important;
}}

/* ── Review panel entity pills ── */

.entity-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 980px;
    font-size: 13px;
    font-weight: 500;
    border: 1px solid {COLORS["border"]};
    background: {COLORS["bg_secondary"]};
    transition: all 0.2s ease;
}}

.entity-pill.rejected {{
    opacity: 0.4;
    text-decoration: line-through;
}}

.entity-pill .category {{
    font-size: 11px;
    color: {COLORS["text_secondary"]};
    text-transform: uppercase;
}}
"""
