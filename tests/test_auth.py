import hashlib
from datetime import timedelta

import pytest


@pytest.fixture
def auth(database):
    import auth
    return auth


def test_create_and_sign_in(auth):
    assert auth.create_user("alice", "Alice@Example.com", "password-123")[0]
    user, err = auth.verify_user("ALICE", "password-123")
    assert user and user["email"] == "alice@example.com" and err == ""
    assert auth.verify_user("alice@example.com", "password-123")[0]
    assert auth.verify_user("alice", "wrong-pass")[0] is None


def test_validation_and_duplicates(auth):
    assert not auth.create_user("<b>", "x@example.com", "password-123")[0]
    assert not auth.create_user("bob", "not-an-email", "password-123")[0]
    assert not auth.create_user("bob", "bob@example.com", "short")[0]
    auth.create_user("bob", "bob@example.com", "password-123")
    assert auth.create_user("BOB", "other@example.com", "password-123")[1] == "That username is taken."


def test_legacy_sha256_hash_is_upgraded(auth):
    import db
    with db.connect() as conn:
        conn.execute("INSERT INTO users (username, email, password, created, email_verified) VALUES (?,?,?,?,1)",
                     ("old", "old@example.com", hashlib.sha256(b"oldpassword").hexdigest(), "2024-01-01"))
    assert auth.verify_user("old", "oldpassword")[0]
    with db.connect() as conn:
        assert conn.execute("SELECT password FROM users WHERE username='old'").fetchone()[0].startswith("scrypt$")


def test_lockout_after_repeated_failures(auth):
    auth.create_user("carol", "carol@example.com", "password-123")
    for _ in range(auth.MAX_FAILED_LOGINS):
        auth.verify_user("carol", "nope-nope")
    user, err = auth.verify_user("carol", "password-123")
    assert user is None and "Too many failed attempts" in err


def test_sessions_and_sign_out_everywhere(auth):
    auth.create_user("dave", "dave@example.com", "password-123")
    uid = auth.verify_user("dave", "password-123")[0]["id"]
    t1, t2 = auth.create_session(uid), auth.create_session(uid)
    assert auth.user_from_session(t1)["username"] == "dave"
    auth.delete_session(t1)
    assert auth.user_from_session(t1) is None and auth.user_from_session(t2)
    auth.delete_all_sessions(uid)
    assert auth.user_from_session(t2) is None
    assert auth.user_from_session("x" * 500) is None


def test_password_reset_token_is_single_use_and_expires(auth, monkeypatch):
    auth.create_user("erin", "erin@example.com", "password-123")
    uid = auth.verify_user("erin", "password-123")[0]["id"]
    session = auth.create_session(uid)
    token = auth._issue_token(uid, "reset", auth.RESET_TTL)
    assert auth.reset_password(token, "brand-new-pass")[0]
    assert not auth.reset_password(token, "another-pass")[0]              # single use
    assert auth.user_from_session(session) is None                       # other sessions signed out
    assert auth.verify_user("erin", "brand-new-pass")[0]
    expired = auth._issue_token(uid, "reset", timedelta(seconds=-1))
    assert not auth.reset_password(expired, "whatever-pass")[0]
    verify = auth._issue_token(uid, "verify", auth.VERIFY_TTL)
    assert not auth.reset_password(verify, "wrong-purpose")[0]           # tokens are purpose-bound


def test_reset_request_without_email_server_says_so(auth, monkeypatch):
    import mailer
    monkeypatch.setattr(mailer, "is_configured", lambda: False)
    assert "isn't set up" in auth.request_password_reset("anyone@example.com")


def test_email_verification_gates_the_digest(auth):
    auth.create_user("fay", "fay@example.com", "password-123")
    user = auth.verify_user("fay", "password-123")[0]
    assert not user["email_verified"]
    assert all(r["email"] != "fay@example.com" for r in auth.get_digest_recipients())
    assert auth.verify_email(auth._issue_token(user["id"], "verify", auth.VERIFY_TTL)) == "fay@example.com"
    assert any(r["email"] == "fay@example.com" for r in auth.get_digest_recipients())


def test_change_password_keeps_current_session_only(auth):
    auth.create_user("gus", "gus@example.com", "password-123")
    uid = auth.verify_user("gus", "password-123")[0]["id"]
    keep, other = auth.create_session(uid), auth.create_session(uid)
    assert not auth.change_password(uid, "wrong", "new-password-1")[0]
    assert auth.change_password(uid, "password-123", "new-password-1", keep_token=keep)[0]
    assert auth.user_from_session(keep) and auth.user_from_session(other) is None


def test_preferences_round_trip(auth):
    auth.create_user("hal", "hal@example.com", "password-123")
    uid = auth.verify_user("hal", "password-123")[0]["id"]
    auth.save_portfolio(uid, {"USDC": 1000.0})
    auth.save_alert_prefs(uid, {"enabled": True, "thresholds": {"USDC": 40}})
    assert auth.load_portfolio(uid) == {"USDC": 1000.0}
    assert auth.load_alert_prefs(uid)["thresholds"]["USDC"] == 40


def test_delete_account_removes_everything(auth):
    import db, notify                                                          # noqa: E401
    auth.create_user("zed", "zed@example.com", "password-123", accepted_terms=True)
    uid = auth.verify_user("zed", "password-123")[0]["id"]
    session = auth.create_session(uid)
    auth._issue_token(uid, "reset", auth.RESET_TTL)
    notify._set_state(uid, "risk:USDC", True)
    with db.connect() as conn:
        assert conn.execute("SELECT terms_accepted FROM users WHERE id=?", (uid,)).fetchone()[0]
    assert not auth.delete_account(uid, "wrong-password")[0]
    assert auth.delete_account(uid, "password-123")[0]
    assert auth.user_from_session(session) is None and auth.get_user(uid) is None
    with db.connect() as conn:
        for table in ("sessions", "auth_tokens", "alert_state"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=?", (uid,)).fetchone()[0] == 0
    assert auth.create_user("zed", "zed@example.com", "password-123")[0]      # name and email are free again
