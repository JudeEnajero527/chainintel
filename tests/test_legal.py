import legal


def test_pages_use_the_contact_address(monkeypatch):
    monkeypatch.setenv("CHAININTEL_CONTACT_EMAIL", "privacy@example.org")
    for text in (legal.terms_markdown(), legal.privacy_markdown()):
        assert "mailto:privacy@example.org" in text
        assert legal.EFFECTIVE_DATE in text


def test_privacy_policy_matches_what_the_app_stores():
    """If you add a column to `users`, describe it in the Privacy Policy and add it here."""
    import auth
    described = {
        "failed_logins": "failed sign-in", "locked_until": "lock out", "digest_opt_in": "daily digest",
        "unsubscribe_token": "unsubscribe", "alert_prefs": "Alert thresholds", "portfolio": "Portfolio holdings",
        "email_verified": "confirmed your email", "notify_prefs": "Discord webhook", "terms_accepted": "agreed to these policies",
    }
    assert set(auth._EXTRA_COLUMNS) == set(described), "new user column — update the Privacy Policy and this test"
    text = legal.privacy_markdown()
    for phrase in described.values():
        assert phrase.lower() in text.lower(), phrase


def test_terms_say_not_financial_advice():
    assert "not financial" in legal.terms_markdown().lower()


def _signals(monkeypatch, on: bool):
    import config
    monkeypatch.setattr(config, "_DOTENV", {})
    monkeypatch.setattr(config, "_SECRETS", {})
    if on:
        monkeypatch.setenv("CHAININTEL_SHOW_SIGNALS", "1")
    else:
        monkeypatch.delenv("CHAININTEL_SHOW_SIGNALS", raising=False)


def test_nothing_points_to_hidden_pages(monkeypatch):
    import auth
    _signals(monkeypatch, on=False)
    text = legal.privacy_markdown()
    assert "Portfolio page" not in text and "Settings and Portfolio" not in text
    assert "Portfolio holdings" in text                       # the stored data is still disclosed
    assert "Whale" not in auth._left_panel()
    _signals(monkeypatch, on=True)
    assert "Portfolio page" in legal.privacy_markdown()
    assert "Whale" in auth._left_panel()
