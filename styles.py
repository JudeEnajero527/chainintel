"""Shared CSS + small HTML/format helpers for every page."""
import html

BASE_CSS = """
<style>
  /* ── Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

  /* ── Root tokens ── */
  :root {
    --bg-base:        #080910;
    --bg-surface:     #0d0f14;
    --bg-elevated:    #12151c;
    --bg-card:        rgba(255,255,255,0.03);
    --border-subtle:  rgba(255,255,255,0.06);
    --border-default: rgba(255,255,255,0.08);
    --border-hover:   rgba(59,130,246,0.35);
    --text-primary:   #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted:     #64748b;
    --blue:           #3b82f6;
    --green:          #22c55e;
    --yellow:         #f59e0b;
    --red:            #ef4444;
    --purple:         #a78bfa;
    --radius-sm:  10px;
    --radius-md:  16px;
    --radius-lg:  24px;
    --shadow-sm:  0 2px 8px rgba(0,0,0,0.4);
    --shadow-md:  0 4px 24px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04);
    --shadow-lg:  0 8px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06);
  }

  /* ── Base ── */
  *, *::before, *::after { box-sizing: border-box; }
  html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg-base) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  }
  [data-testid="stSidebar"] {
    background: var(--bg-surface) !important;
    border-right: 1px solid var(--border-subtle) !important;
  }
  * { font-family: 'Inter', -apple-system, sans-serif !important; }
  #MainMenu, footer, header { visibility: hidden; }
  [data-testid="stDecoration"] { display: none; }

  /* Tighten Streamlit default padding */
  .block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; }

  /* ── Cards ── */
  .card {
    background: var(--bg-card);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: 24px;
    margin-bottom: 14px;
    box-shadow: var(--shadow-md);
    transition: border-color .2s ease, box-shadow .2s ease, transform .15s ease;
  }
  .card:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-lg), 0 0 0 1px rgba(59,130,246,0.08);
    transform: translateY(-1px);
  }
  .card-sm {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 14px 18px;
    margin-bottom: 8px;
    box-shadow: var(--shadow-sm);
    transition: border-color .2s ease;
  }
  .card-sm:hover { border-color: var(--border-hover); }

  /* ── Typography ── */
  .card-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .12em;
    margin-bottom: 10px;
  }
  .card-value {
    font-size: 28px;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.05;
    letter-spacing: -.5px;
  }
  .card-sub {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 6px;
    line-height: 1.4;
  }
  .section-title {
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .14em;
    margin: 32px 0 14px;
  }

  /* ── Status pills ── */
  .pill-stable {
    background: rgba(34,197,94,.12);
    color: var(--green);
    border: 1px solid rgba(34,197,94,.25);
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
    white-space: nowrap;
    letter-spacing: .02em;
  }
  .pill-warning {
    background: rgba(245,158,11,.12);
    color: var(--yellow);
    border: 1px solid rgba(245,158,11,.25);
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
    white-space: nowrap;
    letter-spacing: .02em;
  }
  .pill-critical {
    background: rgba(239,68,68,.12);
    color: var(--red);
    border: 1px solid rgba(239,68,68,.25);
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
    white-space: nowrap;
    letter-spacing: .02em;
  }

  /* ── Risk bars ── */
  .risk-bar-bg {
    background: rgba(255,255,255,0.06);
    border-radius: 999px;
    height: 5px;
    overflow: hidden;
    margin-top: 10px;
  }
  .risk-bar-fill-green  { background: linear-gradient(90deg, #16a34a, #22c55e); height: 5px; border-radius: 999px; transition: width .6s ease; }
  .risk-bar-fill-yellow { background: linear-gradient(90deg, #d97706, #f59e0b); height: 5px; border-radius: 999px; transition: width .6s ease; }
  .risk-bar-fill-red    { background: linear-gradient(90deg, #dc2626, #ef4444); height: 5px; border-radius: 999px; transition: width .6s ease; }

  /* ── News cards ── */
  .news-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 14px 18px;
    margin-bottom: 8px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    transition: border-color .2s ease, background .2s ease;
  }
  .news-card:hover { background: rgba(255,255,255,0.05); border-color: var(--border-default); }
  .news-dot-green  { width: 7px; height: 7px; border-radius: 50%; background: var(--green);  margin-top: 5px; flex-shrink: 0; box-shadow: 0 0 6px rgba(34,197,94,.5); }
  .news-dot-red    { width: 7px; height: 7px; border-radius: 50%; background: var(--red);    margin-top: 5px; flex-shrink: 0; box-shadow: 0 0 6px rgba(239,68,68,.5); }
  .news-dot-yellow { width: 7px; height: 7px; border-radius: 50%; background: var(--yellow); margin-top: 5px; flex-shrink: 0; box-shadow: 0 0 6px rgba(245,158,11,.5); }
  .news-text { font-size: 13px; color: var(--text-secondary); line-height: 1.55; }
  .news-badge-pos { font-size: 10px; font-weight: 700; color: var(--green);  background: rgba(34,197,94,.1);  border: 1px solid rgba(34,197,94,.2);  border-radius: 5px; padding: 2px 8px; display: inline-block; margin-bottom: 4px; letter-spacing: .06em; }
  .news-badge-neg { font-size: 10px; font-weight: 700; color: var(--red);    background: rgba(239,68,68,.1);  border: 1px solid rgba(239,68,68,.2);  border-radius: 5px; padding: 2px 8px; display: inline-block; margin-bottom: 4px; letter-spacing: .06em; }
  .news-badge-neu { font-size: 10px; font-weight: 700; color: var(--yellow); background: rgba(245,158,11,.1); border: 1px solid rgba(245,158,11,.2); border-radius: 5px; padding: 2px 8px; display: inline-block; margin-bottom: 4px; letter-spacing: .06em; }

  /* ── Whale cards ── */
  .whale-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 16px 20px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: border-color .2s ease;
  }
  .whale-card:hover { border-color: var(--border-hover); }
  .whale-amount { font-size: 16px; font-weight: 700; color: var(--text-primary); letter-spacing: -.3px; }
  .whale-addr   { font-size: 11px; color: var(--text-muted); margin-top: 3px; font-family: 'SF Mono', monospace !important; }

  /* ── Sidebar nav links ── */
  [data-testid="stPageLink"] a {
    display: block;
    padding: 9px 12px !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: var(--text-secondary) !important;
    text-decoration: none !important;
    transition: background .15s ease, color .15s ease !important;
    margin-bottom: 2px;
  }
  [data-testid="stPageLink"] a:hover {
    background: rgba(255,255,255,0.06) !important;
    color: var(--text-primary) !important;
  }
  [data-testid="stPageLink"][aria-current] a,
  [data-testid="stPageLink"] a[aria-current="page"] {
    background: rgba(59,130,246,0.12) !important;
    color: var(--blue) !important;
    font-weight: 600 !important;
  }

  /* ── Radio (asset selector) ── */
  [data-testid="stRadio"] label {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    padding: 9px 13px !important;
    margin-bottom: 4px !important;
    color: var(--text-secondary) !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    transition: all .15s ease !important;
  }
  [data-testid="stRadio"] label:hover { border-color: var(--border-default) !important; color: var(--text-primary) !important; }
  [data-testid="stRadio"] label:has(input:checked) {
    border-color: rgba(59,130,246,0.4) !important;
    background: rgba(59,130,246,0.08) !important;
    color: var(--text-primary) !important;
  }

  /* ── Tabs ── */
  [data-testid="stTabs"] button {
    color: var(--text-muted) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    background: transparent !important;
    letter-spacing: .01em;
  }
  [data-testid="stTabs"] button:hover { color: var(--text-secondary) !important; }
  [data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    border-bottom-color: var(--blue) !important;
  }

  /* ── Inputs & sliders ── */
  [data-testid="stNumberInput"] input,
  [data-testid="stTextInput"] input {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-size: 14px !important;
  }
  [data-testid="stNumberInput"] input:focus,
  [data-testid="stTextInput"] input:focus {
    border-color: rgba(59,130,246,0.5) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
  }
  [data-testid="stSlider"] [data-testid="stTickBarMin"],
  [data-testid="stSlider"] [data-testid="stTickBarMax"] { color: var(--text-muted) !important; }

  /* ── Select slider ── */
  [data-baseweb="select"] {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: 8px !important;
  }

  /* ── Spinner ── */
  [data-testid="stSpinner"] { color: var(--text-muted) !important; }

  /* ── Hide Streamlit auto-generated sidebar nav ── */
  [data-testid="stSidebarNav"] { display: none !important; }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 999px; }

  /* ── Animations ── */
  @keyframes fadeUp   { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
  @keyframes fadeIn   { from{opacity:0} to{opacity:1} }
  @keyframes pulse    { 0%,100%{opacity:1} 50%{opacity:.35} }
  @keyframes glow     { 0%,100%{box-shadow:0 0 12px rgba(59,130,246,.3)} 50%{box-shadow:0 0 24px rgba(59,130,246,.6)} }
  @keyframes ticker   { from{transform:translateX(0)} to{transform:translateX(-33.33%)} }
  @keyframes gradientShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }

  .fade-up   { animation: fadeUp .5s ease forwards; }
  .fade-in   { animation: fadeIn .4s ease forwards; }
  .live-dot  { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; margin-right:6px; box-shadow:0 0 6px rgba(34,197,94,.6); vertical-align:middle; }

  /* ── Gradient text ── */
  .gradient-text {
    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 40%, #f472b6 80%);
    background-size: 200% 200%;
    animation: gradientShift 4s ease infinite;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  /* ── Ticker bar ── */
  .ticker-wrap {
    overflow: hidden;
    background: rgba(255,255,255,0.02);
    border-bottom: 1px solid var(--border-subtle);
    padding: 10px 0;
    margin-bottom: 8px;
  }
  .ticker-inner {
    display: inline-block;
    white-space: nowrap;
    animation: ticker 35s linear infinite;
  }
  .ticker-inner:hover { animation-play-state: paused; }

  /* ── Glow card variant ── */
  .card-glow {
    background: var(--bg-card);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(59,130,246,.25);
    border-radius: var(--radius-md);
    padding: 24px;
    margin-bottom: 14px;
    box-shadow: var(--shadow-md), 0 0 30px rgba(59,130,246,.08);
    animation: glow 3s ease-in-out infinite;
  }

  /* ── Stat card ── */
  .stat-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 18px 20px;
    text-align: center;
    transition: all .2s ease;
  }
  .stat-card:hover { border-color: var(--border-default); background: rgba(255,255,255,0.04); }

  /* ── Asset card ── */
  .asset-card {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 20px;
    height: 100%;
    transition: all .2s ease;
    cursor: pointer;
  }
  .asset-card:hover {
    border-color: rgba(59,130,246,.3);
    transform: translateY(-3px);
    box-shadow: 0 12px 40px rgba(0,0,0,.5), 0 0 0 1px rgba(59,130,246,.1);
  }

  /* ── Divider ── */
  .divider { border: none; border-top: 1px solid var(--border-subtle); margin: 24px 0; }

  /* ── Table-like row ── */
  .data-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-radius: 10px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    margin-bottom: 6px;
    transition: all .15s ease;
  }
  .data-row:hover { background: rgba(255,255,255,0.04); border-color: var(--border-default); }

  .pill-unknown {
    background: rgba(148,163,184,.10); color: var(--text-secondary);
    border: 1px solid rgba(148,163,184,.22); border-radius: 999px;
    padding: 4px 14px; font-size: 12px; font-weight: 600; display: inline-block; white-space: nowrap;
  }
  .asset-card-v2 [class^='pill-'], .card [class^='pill-'] { padding: 3px 10px; font-size: 11px; }
  .muted { color: var(--text-muted); }
  .note  { font-size: 12px; color: var(--text-muted); line-height: 1.6; }
  .footer-note { font-size: 11px; color: var(--text-muted); margin-top: 24px; text-align: center; }
  .page-title { font-size: 32px; font-weight: 800; color: var(--text-primary); letter-spacing: -1px; }
  .page-sub   { font-size: 15px; color: var(--text-secondary); margin-top: 6px; }
  .banner {
    border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; font-size: 13px; line-height: 1.6;
    background: rgba(59,130,246,.06); border: 1px solid rgba(59,130,246,.22); color: var(--text-secondary);
  }
  .banner-warn { background: rgba(245,158,11,.07); border-color: rgba(245,158,11,.3); }
  .banner-bad  { background: rgba(239,68,68,.07);  border-color: rgba(239,68,68,.3); }
  .empty { text-align: center; padding: 48px 24px; }
  .empty-icon { font-size: 32px; margin-bottom: 10px; }
  .empty-title { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
  .empty-body { font-size: 13px; color: var(--text-secondary); max-width: 460px; margin: 0 auto; }
  a.row-link { text-decoration: none !important; }
</style>
"""


LEVEL_HEX   = {"stable": "#22c55e", "elevated": "#f59e0b", "critical": "#ef4444", "unknown": "#94a3b8"}
LEVEL_TEXT  = {"stable": "Stable", "elevated": "Elevated", "critical": "Critical", "unknown": "No data"}
LEVEL_PILL  = {"stable": "pill-stable", "elevated": "pill-warning", "critical": "pill-critical", "unknown": "pill-unknown"}


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
        return f'{lbl}<div style="font-size:22px;font-weight:800;color:var(--text-muted);">—</div><div class="card-sub">Unavailable</div>'
    return f"""
    {lbl}
    <div style="font-size:22px;font-weight:800;color:{risk_hex(score)};letter-spacing:-.5px;">{score:.1f}<span style="font-size:13px;color:var(--text-muted);font-weight:500;">/100</span></div>
    <div class="risk-bar-bg"><div class="risk-bar-fill-{risk_color(score)}" style="width:{min(score, 100)}%;"></div></div>
    """


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
    """Simple metric card. `value`/`sub` may contain trusted HTML; escape external text before passing it."""
    style = f' style="border-color:{border}33;"' if border else ""
    vstyle = f' style="color:{color};"' if color else ""
    sub_html = f'<div class="card-sub">{sub}</div>' if sub else ""
    return f'<div class="card"{style}><div class="card-label">{esc(label)}</div><div class="card-value"{vstyle}>{value}</div>{sub_html}</div>'


def empty_state(icon, title, body=""):
    return f'<div class="card empty"><div class="empty-icon">{icon}</div><div class="empty-title">{esc(title)}</div><div class="empty-body">{body}</div></div>'


def section(title):
    return f'<div class="section-title">{esc(title)}</div>'


# Shared Plotly layout for the dark theme.
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#94a3b8"),
    margin=dict(t=10, b=10, l=10, r=10),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zeroline=False),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", zeroline=False),
    hoverlabel=dict(bgcolor="#12151c", bordercolor="#334155", font=dict(family="Inter", color="#f1f5f9")),
)
