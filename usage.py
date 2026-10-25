"""
Anonymous usage evidence: daily page-view counts and an optional "How are you using ChainIntel?" form.

Privacy: no cookies, no IP addresses, no browser details. A visit is identified only by a random ID that lives
in the Streamlit session (one browser tab session), so the same person on two days counts twice.
Report:  python3 research/usage_report.py
"""
import uuid
from datetime import datetime, timezone

import streamlit as st

import db

_READY = "_usage_tables_ready"


def _init():
    if st.session_state.get(_READY):
        return
    with db.connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS page_views (
                            day TEXT NOT NULL, page TEXT NOT NULL, visitor TEXT NOT NULL, signed_in INTEGER NOT NULL,
                            PRIMARY KEY (day, page, visitor))""")
        conn.execute(f"""CREATE TABLE IF NOT EXISTS usage_feedback (
                            id {db.AUTO_ID}, created TEXT NOT NULL, role TEXT, use_case TEXT NOT NULL,
                            contact TEXT, signed_in INTEGER NOT NULL)""")
    st.session_state[_READY] = True


def record_view(page: str):
    """Count one view of `page` today for this browser session (repeat views the same day count once)."""
    try:
        _init()
        visitor = st.session_state.setdefault("_visitor_id", uuid.uuid4().hex)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"_viewed_{day}_{page}"
        if st.session_state.get(key):
            return
        with db.connect() as conn:
            try:
                conn.execute("INSERT INTO page_views (day, page, visitor, signed_in) VALUES (?,?,?,?)",
                             (day, page, visitor, int(bool(st.session_state.get("user")))))
            except db.IntegrityError:
                pass
        st.session_state[key] = True
    except Exception:          # counting must never break a page
        pass


ROLES = ["", "Researcher / academic", "Risk or compliance professional", "Investor or trader",
         "Developer / protocol team", "Journalist", "Student", "Other"]


def render_feedback_form():
    """Optional, anonymous unless the visitor leaves contact details."""
    with st.expander("How are you using ChainIntel? (optional, 30 seconds)"):
        if st.session_state.get("_feedback_sent"):
            st.success("Thank you. Your feedback was saved.")
            return
        with st.form("usage_feedback", clear_on_submit=True):
            role = st.selectbox("You are a…", ROLES, index=0)
            use_case = st.text_area("What do you use it for, or what would make it more useful?", max_chars=1000)
            contact = st.text_input("Email or name, only if you're happy for us to follow up (optional)", max_chars=200)
            sent = st.form_submit_button("Send")
        if sent:
            if not use_case.strip():
                st.error("Please write a sentence about how you use it.")
                return
            try:
                _init()
                with db.connect() as conn:
                    conn.execute("INSERT INTO usage_feedback (created, role, use_case, contact, signed_in) VALUES (?,?,?,?,?)",
                                 (datetime.now(timezone.utc).isoformat(timespec="seconds"), role or None,
                                  use_case.strip(), contact.strip() or None, int(bool(st.session_state.get("user")))))
                st.session_state["_feedback_sent"] = True
                st.rerun()
            except Exception:
                st.error("Sorry, that didn't save. Please try again.")
