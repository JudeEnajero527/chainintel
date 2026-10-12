import json

import pytest


def assessment(risk, price=1.0, off_peg=False):
    return {"price": price, "risk": {"total": risk, "peg": 0, "liquidity": 0, "sentiment": 0},
            "ml": {"label": "Off peg now" if off_peg else "Low risk"}}


def test_alert_fires_once_then_recovers_with_margin():
    import notify
    th = {"USDC": 50}
    ev = notify.events_for(th, {}, {"USDC": assessment(55)})
    assert [(k, a) for k, a, *_ in ev] == [("risk:USDC", True)]
    state = {"risk:USDC": True}
    assert notify.events_for(th, state, {"USDC": assessment(60)}) == []          # no repeat
    assert notify.events_for(th, state, {"USDC": assessment(47)}) == []          # inside the recovery margin
    ev = notify.events_for(th, state, {"USDC": assessment(40)})
    assert [(k, a) for k, a, *_ in ev] == [("risk:USDC", False)]


def test_off_peg_events():
    import notify
    ev = notify.events_for({}, {}, {"FRAX": assessment(10, price=0.99, off_peg=True)})
    assert ("peg:FRAX", True) in [(k, a) for k, a, *_ in ev]
    ev = notify.events_for({}, {"peg:FRAX": True}, {"FRAX": assessment(10, price=0.9995)})
    assert ("peg:FRAX", False) in [(k, a) for k, a, *_ in ev]


def test_discord_webhook_validation():
    import notify
    assert notify.valid_discord_webhook("https://discord.com/api/webhooks/123/abc-DEF_9")
    assert not notify.valid_discord_webhook("https://evil.example.com/api/webhooks/123/abc")
    assert not notify.valid_discord_webhook("http://discord.com/api/webhooks/123/abc")


def test_process_alerts_delivers_once(database, monkeypatch):
    import auth, notify                                                       # noqa: E401
    auth.create_user("ivy", "ivy@example.com", "password-123")
    uid = auth.verify_user("ivy", "password-123")[0]["id"]
    auth.save_alert_prefs(uid, {"enabled": True, "thresholds": {"USDC": 50}})
    auth.save_notify_prefs(uid, {"email": False, "discord_webhook": "https://discord.com/api/webhooks/1/x", "telegram_chat_id": ""})
    sent = []

    class Resp:
        status_code = 204

    monkeypatch.setattr(notify.requests, "post", lambda url, **kw: sent.append(kw["json"]["content"]) or Resp())
    data = {"USDC": assessment(70)}
    assert notify.process_alerts(data) == 1
    assert notify.process_alerts(data) == 0
    assert "USDC" in sent[0]
