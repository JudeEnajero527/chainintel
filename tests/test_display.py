import config
from styles import fmt_prob


def test_fmt_prob_never_shows_zero():
    assert fmt_prob(0.0) == "<0.1%"
    assert fmt_prob(0.04) == "<0.1%"
    assert fmt_prob(0.4) == "0.4%"
    assert fmt_prob(13.5) == "13.5%"
    assert fmt_prob(None) == "—"
    assert fmt_prob(None, missing="Off peg") == "Off peg"


def test_signal_pages_hidden_by_default(monkeypatch):
    monkeypatch.delenv("CHAININTEL_SHOW_SIGNALS", raising=False)
    monkeypatch.setattr(config, "_DOTENV", {})
    monkeypatch.setattr(config, "_SECRETS", {})
    assert config.show_signals() is False
    monkeypatch.setenv("CHAININTEL_SHOW_SIGNALS", "1")
    assert config.show_signals() is True
