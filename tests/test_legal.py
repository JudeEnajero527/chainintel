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
