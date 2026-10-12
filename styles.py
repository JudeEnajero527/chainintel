"""Design system: CSS tokens + components, Plotly template, and small HTML/format helpers."""
import html

import plotly.graph_objects as go
import plotly.io as pio

BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
  --bg:        #080a10;
  --surface:   #0f1219;
  --surface-2: #151a25;
  --border:    rgba(148,163,184,.13);
  --border-2:  rgba(148,163,184,.24);
  --text:      #e8edf5;
  --text-2:    #a3b0c2;
  --muted:     #6b7a90;
  --accent:    #4f8cff;
  --green:     #22c55e;
  --amber:     #f59e0b;
  --red:       #ef4444;
  --violet:    #a78bfa;
  --radius:    14px;
}

html, body, [data-testid="stAppViewContainer"] { background: var(--bg) !important; }
html, body, p, div, span, label, input, button, textarea, h1, h2, h3, h4, li, td, th {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
[data-testid="stMain"] { font-variant-numeric: tabular-nums; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 2.2rem !important; padding-bottom: 3rem !important; max-width: 1320px; }

/* ── Sidebar + navigation ── */
[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebarNav"] a { border-radius: 8px; padding: 6px 10px; }
[data-testid="stSidebarNav"] a span { color: var(--text-2) !important; font-size: 14px; font-weight: 500; }
[data-testid="stSidebarNav"] a:hover { background: rgba(148,163,184,.08) !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: rgba(79,140,255,.13) !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: var(--text) !important; font-weight: 600; }
[data-testid="stNavSectionHeader"] span, [data-testid="stSidebarNav"] header span {
  color: var(--muted) !important; font-size: 11px !important; font-weight: 700 !important;
  letter-spacing: .1em; text-transform: uppercase;
}
[data-testid="stLogo"] { height: 2.1rem; max-width: 100%; }

/* ── Typography ── */
.page-title { font-size: 30px; font-weight: 800; color: var(--text); letter-spacing: -.8px; line-height: 1.15; }
.page-sub   { font-size: 15px; color: var(--text-2); margin-top: 6px; }
.section-title {
  display: flex; align-items: center; gap: 12px;
  font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .12em;
  margin: 30px 0 12px;
}
.section-title::after { content: ""; flex: 1; height: 1px; background: var(--border); }
.note { font-size: 12px; color: var(--muted); line-height: 1.6; }
.footer-note { font-size: 11px; color: var(--muted); margin-top: 28px; text-align: center; }
code { font-size: 12px !important; }

/* ── Cards ── */
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 18px 20px; margin-bottom: 12px; transition: border-color .15s ease;
}
.card:hover { border-color: var(--border-2); }
.card-sm { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; }
.card-label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; }
.card-value { font-size: 26px; font-weight: 800; color: var(--text); line-height: 1.1; letter-spacing: -.6px; }
.card-sub   { font-size: 12px; color: var(--text-2); margin-top: 6px; line-height: 1.45; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: var(--radius) !important; }

/* ── Status pills ── */
.pill-stable, .pill-warning, .pill-critical, .pill-unknown {
  display: inline-flex; align-items: center; gap: 5px; white-space: nowrap;
  border-radius: 999px; padding: 3px 10px; font-size: 11.5px; font-weight: 600; border: 1px solid;
}
.pill-stable   { color: var(--green); background: rgba(34,197,94,.10);  border-color: rgba(34,197,94,.25); }
.pill-warning  { color: var(--amber); background: rgba(245,158,11,.10); border-color: rgba(245,158,11,.28); }
.pill-critical { color: var(--red);   background: rgba(239,68,68,.10);  border-color: rgba(239,68,68,.28); }
.pill-unknown  { color: var(--text-2); background: rgba(148,163,184,.08); border-color: rgba(148,163,184,.22); }

/* ── Risk bars ── */
.risk-bar-bg { background: rgba(148,163,184,.12); border-radius: 999px; height: 5px; overflow: hidden; margin-top: 10px; }
.risk-bar-fill-green  { background: var(--green); height: 5px; border-radius: 999px; }
.risk-bar-fill-yellow { background: var(--amber); height: 5px; border-radius: 999px; }
.risk-bar-fill-red    { background: var(--red);   height: 5px; border-radius: 999px; }

/* ── Status banner (Overview) ── */
.status {
  display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  border-radius: var(--radius); padding: 18px 22px; margin-bottom: 16px; border: 1px solid;
}
.status-title { font-size: 20px; font-weight: 800; letter-spacing: -.4px; }
.status-sub { font-size: 13px; color: var(--text-2); margin-top: 3px; }
.status-stable   { background: linear-gradient(90deg, rgba(34,197,94,.10), rgba(34,197,94,.02));  border-color: rgba(34,197,94,.25); }
.status-elevated { background: linear-gradient(90deg, rgba(245,158,11,.11), rgba(245,158,11,.02)); border-color: rgba(245,158,11,.28); }
.status-critical { background: linear-gradient(90deg, rgba(239,68,68,.12), rgba(239,68,68,.02));  border-color: rgba(239,68,68,.30); }
.status-unknown  { background: var(--surface); border-color: var(--border); }

/* ── Lists ── */
.news-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 12px 16px; margin-bottom: 8px; display: flex; align-items: flex-start; gap: 12px;
}
.news-card:hover { border-color: var(--border-2); }
.news-dot-green, .news-dot-red, .news-dot-yellow { width: 7px; height: 7px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; }
.news-dot-green { background: var(--green); } .news-dot-red { background: var(--red); } .news-dot-yellow { background: var(--amber); }
.news-text { font-size: 13.5px; color: var(--text); line-height: 1.5; }
.news-badge-pos, .news-badge-neg, .news-badge-neu {
  font-size: 10px; font-weight: 700; border-radius: 5px; padding: 1px 7px; display: inline-block; margin-bottom: 4px;
  letter-spacing: .05em; text-transform: uppercase;
}
.news-badge-pos { color: var(--green); background: rgba(34,197,94,.10); }
.news-badge-neg { color: var(--red);   background: rgba(239,68,68,.10); }
.news-badge-neu { color: var(--amber); background: rgba(245,158,11,.10); }
.whale-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; margin-bottom: 8px;
  display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
}
.whale-amount { font-size: 16px; font-weight: 700; letter-spacing: -.3px; }
.whale-addr { font-size: 12px; color: var(--muted); margin-top: 3px; font-family: 'SF Mono', ui-monospace, monospace; }
.data-row {
  display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-radius: 10px;
  background: var(--surface); border: 1px solid var(--border); margin-bottom: 6px;
}
.data-row:hover { border-color: var(--border-2); }
a.row-link, a.row-link:hover { text-decoration: none !important; color: inherit !important; }

/* ── Banners + empty states ── */
.banner {
  border-radius: 12px; padding: 13px 17px; margin-bottom: 16px; font-size: 13px; line-height: 1.6; color: var(--text-2);
  background: rgba(79,140,255,.06); border: 1px solid rgba(79,140,255,.22);
}
.banner strong { color: var(--text); }
.banner-warn { background: rgba(245,158,11,.06); border-color: rgba(245,158,11,.28); }
.banner-bad  { background: rgba(239,68,68,.07);  border-color: rgba(239,68,68,.30); }
.empty { text-align: center; padding: 44px 24px; }
.empty-icon  { font-size: 30px; margin-bottom: 10px; }
.empty-title { font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
.empty-body  { font-size: 13px; color: var(--text-2); max-width: 480px; margin: 0 auto; line-height: 1.6; }

.live-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--green);
  margin-right: 6px; vertical-align: middle; animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .35 } }

/* ── Widgets ── */
[data-testid="stSegmentedControl"] button { font-weight: 600; }
[data-testid="stExpander"] details { border-radius: 10px !important; border-color: var(--border) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 10px; }

@media (max-width: 640px) {
  .page-title { font-size: 24px; }
  .card-value { font-size: 22px; }
  .status-title { font-size: 17px; }
}
</style>
"""

LEVEL_HEX  = {"stable": "#22c55e", "elevated": "#f59e0b", "critical": "#ef4444", "unknown": "#94a3b8"}
LEVEL_TEXT = {"stable": "Stable", "elevated": "Elevated", "critical": "Critical", "unknown": "No data"}
LEVEL_PILL = {"stable": "pill-stable", "elevated": "pill-warning", "critical": "pill-critical", "unknown": "pill-unknown"}


def esc(value) -> str:
    """HTML-escape anything that came from a user or an external API before it goes into unsafe_allow_html."""
    return html.escape("" if value is None else str(value))


def risk_level(score):
    if score is None:
        return "unknown"
    return "stable" if score < 30 else "elevated" if score < 60 else "critical"


def risk_color(score):
    """CSS bar suffix: green / yellow / red."""
    return {"stable": "green", "elevated": "yellow", "critical": "red", "unknown": "green"}[risk_level(score)]


def risk_hex(score):
    return LEVEL_HEX[risk_level(score)]


def status_pill(score=None, level=None, text=None):
    level = level or risk_level(score)
    return f'<span class="{LEVEL_PILL[level]}">● {esc(text or LEVEL_TEXT[level])}</span>'


def risk_bar_html(score, label=""):
    lbl = f'<div class="card-label">{esc(label)}</div>' if label else ""
    if score is None:
        return f'{lbl}<div class="card-value" style="color:var(--muted);">—</div><div class="card-sub">Unavailable</div>'
    return (f'{lbl}<div class="card-value" style="font-size:22px;color:{risk_hex(score)};">{score:.1f}'
            f'<span style="font-size:13px;color:var(--muted);font-weight:500;">/100</span></div>'
            f'<div class="risk-bar-bg"><div class="risk-bar-fill-{risk_color(score)}" style="width:{min(score, 100)}%;"></div></div>')


def fmt_price(p):
    return f"${p:.4f}" if p is not None else "N/A"


def fmt_usd(x, digits=1):
    if x is None:
        return "N/A"
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div:
            return f"${x/div:,.{digits}f}{suffix}"
    return f"${x:,.0f}"


def fmt_pct(x, digits=1, signed=True):
    if x is None:
        return "—"
    return f"{x:+.{digits}f}%" if signed else f"{x:.{digits}f}%"


def fmt_age(secs):
    secs = max(0, int(secs))
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
    return f"{secs // 86400}d ago"


def short_addr(addr):
    return f"{addr[:6]}…{addr[-4:]}" if addr and len(addr) > 12 else (addr or "")


def card(label, value, sub="", color=None, border=None):
    """Metric card. `value`/`sub` may contain trusted HTML; escape external text before passing it."""
    style = f' style="border-color:{border}40;"' if border else ""
    vstyle = f' style="color:{color};"' if color else ""
    sub_html = f'<div class="card-sub">{sub}</div>' if sub else ""
    return f'<div class="card"{style}><div class="card-label">{esc(label)}</div><div class="card-value"{vstyle}>{value}</div>{sub_html}</div>'


def empty_state(icon, title, body=""):
    return f'<div class="card empty"><div class="empty-icon">{icon}</div><div class="empty-title">{esc(title)}</div><div class="empty-body">{body}</div></div>'


def section(title):
    return f'<div class="section-title">{esc(title)}</div>'


# ── Plotly: one template for every chart ───────────────────────────────────────
pio.templates["chainintel"] = go.layout.Template(layout=dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif", color="#a3b0c2", size=12),
    colorway=["#4f8cff", "#a78bfa", "#22c55e", "#f59e0b", "#ef4444", "#2dd4bf", "#f472b6", "#94a3b8"],
    xaxis=dict(gridcolor="rgba(148,163,184,.08)", zeroline=False, linecolor="rgba(148,163,184,.15)"),
    yaxis=dict(gridcolor="rgba(148,163,184,.08)", zeroline=False, linecolor="rgba(148,163,184,.15)"),
    hoverlabel=dict(bgcolor="#151a25", bordercolor="#334155", font=dict(color="#e8edf5")),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    margin=dict(t=10, b=10, l=10, r=10),
))
pio.templates.default = "plotly_dark+chainintel"

# Kept for call sites that pass it explicitly; the template already applies these.
PLOT_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=10, b=10, l=10, r=10))
