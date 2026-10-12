"""User accounts: storage, password hashing, login wall, per-user preferences."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import streamlit as st

from styles import esc

DB_PATH = os.getenv("CHAININTEL_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "chainintel.db")

MIN_PASSWORD_LEN = 8
MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# scrypt parameters (OWASP-recommended minimum: N=2^17 is better but slow on small servers)
_N, _R, _P = 2 ** 14, 8, 1

# ── DB setup ────────────────────────────────────────────────────────────────────

_EXTRA_COLUMNS = {
    "failed_logins":     "INTEGER NOT NULL DEFAULT 0",
    "locked_until":      "TEXT",
    "digest_opt_in":     "INTEGER NOT NULL DEFAULT 1",
    "unsubscribe_token": "TEXT",
    "alert_prefs":       "TEXT",
}


def _conn():
    return sqlite3.connect(DB_PATH)


def init_user_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    UNIQUE NOT NULL,
                email      TEXT    UNIQUE NOT NULL,
                password   TEXT    NOT NULL,
                created    TEXT    NOT NULL,
                last_login TEXT
            )""")
        existing = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        for col, ddl in _EXTRA_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        for (uid,) in conn.execute("SELECT id FROM users WHERE unsubscribe_token IS NULL").fetchall():
            conn.execute("UPDATE users SET unsubscribe_token=? WHERE id=?", (secrets.token_urlsafe(24), uid))


def _now():
    return datetime.now(timezone.utc)

# ── Password hashing ────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def _check_password(password: str, stored: str) -> tuple[bool, bool]:
    """Returns (matches, needs_rehash). Accepts legacy unsalted SHA-256 hashes so old accounts still work."""
    if stored.startswith("scrypt$"):
        _, n, r, p, salt, digest = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(digest) // 2)
        return hmac.compare_digest(calc.hex(), digest), int(n) < _N
    legacy = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored), True

# ── User ops ────────────────────────────────────────────────────────────────────

_USER_COLS = "id, username, email, password, failed_logins, locked_until, digest_opt_in"


def _row_to_user(row):
    return {"id": row[0], "username": row[1], "email": row[2], "digest_opt_in": bool(row[6])}


def create_user(username: str, email: str, password: str, digest_opt_in: bool = True) -> tuple[bool, str]:
    username, email = username.strip(), email.strip().lower()
    if not USERNAME_RE.match(username):
        return False, "Username must be 3–32 characters: letters, numbers, dot, dash or underscore."
    if not EMAIL_RE.match(email):
        return False, "Enter a valid email address."
    if len(password) < MIN_PASSWORD_LEN:
        return False, f"Password must be at least {MIN_PASSWORD_LEN} characters."
    with _conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone():
            return False, "That username is taken."
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            return False, "An account with that email already exists — try signing in."
        try:
            conn.execute(
                "INSERT INTO users (username, email, password, created, digest_opt_in, unsubscribe_token) VALUES (?,?,?,?,?,?)",
                (username, email, hash_password(password), _now().isoformat(), int(digest_opt_in), secrets.token_urlsafe(24)),
            )
        except sqlite3.IntegrityError:
            return False, "That username or email is already registered."
    return True, "Account created."


def verify_user(identifier: str, password: str) -> tuple[dict | None, str]:
    """Sign in with username or email. Returns (user, "") or (None, error message)."""
    identifier = identifier.strip()
    with _conn() as conn:
        row = conn.execute(
            f"SELECT {_USER_COLS} FROM users WHERE username = ? COLLATE NOCASE OR email = ?",
            (identifier, identifier.lower()),
        ).fetchone()
        if not row:
            hash_password(password)          # same cost as a real check, so timing doesn't reveal valid usernames
            return None, "Incorrect username or password."
        uid, stored, failed, locked_until = row[0], row[3], row[4], row[5]
        if locked_until and datetime.fromisoformat(locked_until) > _now():
            mins = int((datetime.fromisoformat(locked_until) - _now()).total_seconds() // 60) + 1
            return None, f"Too many failed attempts. Try again in {mins} min."
        ok, needs_rehash = _check_password(password, stored)
        if not ok:
            failed += 1
            lock = (_now() + LOCKOUT).isoformat() if failed >= MAX_FAILED_LOGINS else None
            conn.execute("UPDATE users SET failed_logins=?, locked_until=? WHERE id=?",
                         (0 if lock else failed, lock, uid))
            return None, "Incorrect username or password."
        conn.execute("UPDATE users SET last_login=?, failed_logins=0, locked_until=NULL WHERE id=?", (_now().isoformat(), uid))
        if needs_rehash:
            conn.execute("UPDATE users SET password=? WHERE id=?", (hash_password(password), uid))
    return _row_to_user(row), ""


def get_digest_recipients() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT username, email, unsubscribe_token FROM users WHERE digest_opt_in = 1 ORDER BY created"
        ).fetchall()
    return [{"username": r[0], "email": r[1], "unsubscribe_token": r[2]} for r in rows]


def unsubscribe(token: str) -> str | None:
    """Turns off the digest for the account owning `token`. Returns its email, or None if the token is unknown."""
    with _conn() as conn:
        row = conn.execute("SELECT id, email FROM users WHERE unsubscribe_token = ?", (token,)).fetchone()
        if row:
            conn.execute("UPDATE users SET digest_opt_in = 0 WHERE id = ?", (row[0],))
    return row[1] if row else None


def set_digest_opt_in(user_id: int, on: bool):
    with _conn() as conn:
        conn.execute("UPDATE users SET digest_opt_in = ? WHERE id = ?", (int(on), user_id))


def load_alert_prefs(user_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT alert_prefs FROM users WHERE id = ?", (user_id,)).fetchone()
    return json.loads(row[0]) if row and row[0] else None


def save_alert_prefs(user_id: int, prefs: dict):
    with _conn() as conn:
        conn.execute("UPDATE users SET alert_prefs = ? WHERE id = ?", (json.dumps(prefs), user_id))

# ── Session helpers ─────────────────────────────────────────────────────────────

def is_logged_in() -> bool:
    return bool(st.session_state.get("user"))


def get_current_user() -> dict | None:
    return st.session_state.get("user")


def logout():
    for key in ("user", "alert_thresholds", "alerts_enabled"):
        st.session_state.pop(key, None)

# ── Login wall UI ───────────────────────────────────────────────────────────────

AUTH_CSS = """
<style>
.main .block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stHeader"] { display: none !important; }
[data-testid="stHorizontalBlock"] { gap: 0 !important; }

:is([data-testid="stColumn"], [data-testid="column"]):first-child {
  background: linear-gradient(145deg, #05070f 0%, #0a0e1f 60%, #0d1530 100%);
  min-height: 100vh; padding: 60px 56px !important; position: relative; overflow: hidden;
}
:is([data-testid="stColumn"], [data-testid="column"]):last-child {
  background: linear-gradient(160deg, #0a0e1f 0%, #05070f 50%, #0d1030 100%);
  min-height: 100vh; padding: 72px 48px !important; border-left: 1px solid rgba(59,130,246,.08);
}
:is([data-testid="stColumn"], [data-testid="column"]):last-child > div { max-width: 400px; margin: 0 auto; }
@media (max-width: 900px) {
  :is([data-testid="stColumn"], [data-testid="column"]):first-child { display: none; }
  :is([data-testid="stColumn"], [data-testid="column"]):last-child { padding: 40px 20px !important; border-left: none; }
}

.auth-logo { font-size: 26px; font-weight: 900; color: #f9fafb; letter-spacing: -1px; margin-bottom: 48px; }
.auth-logo span { color: #3b82f6; }
.auth-headline { font-size: 42px; font-weight: 800; color: #f9fafb; letter-spacing: -1.5px; line-height: 1.15; margin-bottom: 18px; }
.auth-headline em {
  font-style: normal; background: linear-gradient(90deg, #3b82f6, #a78bfa);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.auth-tagline { font-size: 15px; color: #94a3b8; line-height: 1.7; max-width: 380px; margin-bottom: 44px; }
.auth-stats { display: flex; gap: 32px; margin-bottom: 44px; }
.auth-stat-num { font-size: 26px; font-weight: 800; color: #f9fafb; letter-spacing: -1px; }
.auth-stat-label { font-size: 12px; color: #64748b; margin-top: 2px; font-weight: 500; }
.auth-feature { display: flex; gap: 14px; margin-bottom: 16px; align-items: flex-start; }
.auth-feature-icon {
  width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0; font-size: 16px;
  background: rgba(59,130,246,.12); border: 1px solid rgba(59,130,246,.2);
  display: flex; align-items: center; justify-content: center;
}
.auth-feature strong { display: block; font-size: 13px; font-weight: 600; color: #e5e7eb; margin-bottom: 2px; }
.auth-feature span { font-size: 12px; color: #64748b; line-height: 1.5; }
.auth-form-title { font-size: 24px; font-weight: 800; color: #f9fafb; letter-spacing: -.6px; margin: 4px 0 4px; }
.auth-form-sub { font-size: 13px; color: #64748b; margin-bottom: 18px; }
.auth-small { font-size: 11px; color: #64748b; text-align: center; margin-top: 14px; line-height: 1.6; }

[data-testid="stForm"] { border: none !important; padding: 0 !important; }
[data-testid="stTextInput"] label p {
  color: #94a3b8 !important; font-size: 11px !important; font-weight: 600 !important;
  letter-spacing: .08em; text-transform: uppercase;
}
[data-testid="stTextInput"] input {
  background: #0d0f1a !important; border: 1px solid #1f2437 !important; color: #f9fafb !important;
  border-radius: 10px !important; font-size: 14px !important; padding: 11px 14px !important;
}
[data-testid="stFormSubmitButton"] button {
  width: 100%; background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important; color: #fff !important;
  border: none !important; border-radius: 10px !important; font-weight: 700 !important; padding: 12px 20px !important;
  box-shadow: 0 4px 20px rgba(59,130,246,.25) !important; margin-top: 6px;
}
[data-testid="stRadio"] > div { display: flex; gap: 4px; background: #0d0f1a; border: 1px solid #1f2437; border-radius: 12px; padding: 4px; }
[data-testid="stRadio"] label {
  flex: 1; justify-content: center; padding: 8px 0 !important; border-radius: 8px !important; margin: 0 !important;
  font-size: 13px !important; font-weight: 600 !important; color: #64748b !important; background: transparent !important; border: none !important;
}
[data-testid="stRadio"] label:has(input:checked) { background: #1a1d2e !important; color: #f9fafb !important; }
[data-testid="stRadio"] label > div:first-child { display: none; }
</style>
"""

LEFT_PANEL = """
<div class="auth-logo">⬡ Chain<span>Intel</span></div>
<div class="auth-headline">Know before<br>the <em>depeg</em><br>happens.</div>
<div class="auth-tagline">
  Risk intelligence for the stablecoin market. Live peg, liquidity and news monitoring for nine
  major stablecoins, plus a 7-day depeg forecast trained on five years of market history.
</div>
<div class="auth-stats">
  <div><div class="auth-stat-num">9</div><div class="auth-stat-label">Stablecoins<br>monitored</div></div>
  <div><div class="auth-stat-num">230</div><div class="auth-stat-label">Coins in model<br>training data</div></div>
  <div><div class="auth-stat-num">7-day</div><div class="auth-stat-label">Depeg<br>forecast</div></div>
</div>
<div class="auth-feature"><div class="auth-feature-icon">📡</div><div>
  <strong>Live peg &amp; liquidity monitoring</strong>
  <span>Price, on-chain DEX depth, and news sentiment rolled into one transparent risk score.</span></div></div>
<div class="auth-feature"><div class="auth-feature-icon">🤖</div><div>
  <strong>Depeg forecasting, honestly evaluated</strong>
  <span>Tested only on data the model never saw — the real accuracy numbers are on the Intelligence page.</span></div></div>
<div class="auth-feature"><div class="auth-feature-icon">🐋</div><div>
  <strong>Whale transfer tracking</strong>
  <span>Large on-chain stablecoin moves, straight from Ethereum via Etherscan.</span></div></div>
<div class="auth-feature"><div class="auth-feature-icon">📬</div><div>
  <strong>Optional daily digest</strong>
  <span>A morning email with every risk score and anything that moved overnight. One-click unsubscribe.</span></div></div>
"""


def _handle_unsubscribe():
    token = st.query_params.get("unsubscribe")
    if not token:
        return
    email = unsubscribe(token)
    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if email:
            st.success(f"{email} has been unsubscribed from the ChainIntel daily digest.")
        else:
            st.error("That unsubscribe link is invalid or has already been used.")
    st.stop()


def render_auth_wall() -> bool:
    """Shows the sign-in / sign-up screen. Returns True once the user is authenticated."""
    if not st.session_state.get("_user_db_ready"):
        init_user_db()
        st.session_state["_user_db_ready"] = True
    _handle_unsubscribe()
    if is_logged_in():
        return True

    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    left, right = st.columns([1, 1])
    with left:
        st.markdown(LEFT_PANEL, unsafe_allow_html=True)

    with right:
        st.markdown('<div class="auth-logo" style="margin-bottom:28px;">⬡ Chain<span>Intel</span></div>', unsafe_allow_html=True)
        mode = st.radio("Mode", ["Sign in", "Create account"], horizontal=True, label_visibility="collapsed", key="auth_tab")

        if mode == "Sign in":
            st.markdown('<div class="auth-form-title">Welcome back</div><div class="auth-form-sub">Sign in to your ChainIntel account</div>', unsafe_allow_html=True)
            with st.form("login_form"):
                ident = st.text_input("Username or email", placeholder="your_username")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Sign in →")
            if submitted:
                if not ident or not password:
                    st.error("Please fill in both fields.")
                else:
                    user, err = verify_user(ident, password)
                    if user:
                        st.session_state["user"] = user
                        st.rerun()
                    st.error(err)
        else:
            st.markdown('<div class="auth-form-title">Create your account</div><div class="auth-form-sub">Free · No credit card</div>', unsafe_allow_html=True)
            with st.form("signup_form"):
                username = st.text_input("Username", placeholder="choose_a_username")
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder=f"at least {MIN_PASSWORD_LEN} characters")
                digest = st.checkbox("Email me the daily risk digest", value=True)
                submitted = st.form_submit_button("Create account →")
            if submitted:
                ok, msg = create_user(username, email, password, digest)
                if ok:
                    user, _ = verify_user(username, password)
                    st.session_state["user"] = user
                    st.rerun()
                st.error(msg)
            st.markdown('<div class="auth-small">You can turn the digest off any time from the sidebar or any email.</div>', unsafe_allow_html=True)

        st.markdown(
            '<div class="auth-small" style="margin-top:28px;">'
            '<span class="live-dot"></span>Data: CoinGecko · DefiLlama · DexScreener · Etherscan</div>',
            unsafe_allow_html=True,
        )
    return False


def signed_in_badge(user: dict) -> str:
    return (
        '<hr style="border:none;border-top:1px solid rgba(255,255,255,.06);margin:16px 0 12px;">'
        '<div style="font-size:12px;color:#64748b;">Signed in as</div>'
        f'<div style="font-size:13px;font-weight:700;color:#f9fafb;margin-bottom:10px;">{esc(user["username"])}</div>'
    )
