"""
Terms of Use and Privacy Policy.

Written to match what the code actually does — if you change what's collected or who it's shared with
(new fields, analytics, a new email provider…), update the Privacy Policy and EFFECTIVE_DATE.
"""
import streamlit as st

import config

EFFECTIVE_DATE = "October 12, 2026"


def contact_email() -> str:
    return config.get("CHAININTEL_CONTACT_EMAIL") or config.get("CHAININTEL_EMAIL")


def _contact_line() -> str:
    email = contact_email()
    return f"[{email}](mailto:{email})" if email else "the contact address shown on this page once the operator has set one"


def terms_markdown() -> str:
    return f"""
# Terms of Use

*Effective {EFFECTIVE_DATE}*

These terms govern your use of ChainIntel ("ChainIntel", "we", "us"), a website that monitors stablecoin
prices, liquidity, news and related signals. By creating an account or using ChainIntel, you agree to these
terms. If you don't agree, please don't use the service.

## 1. Not financial advice

**ChainIntel is an information tool. Nothing on ChainIntel is financial, investment, legal or tax advice**, and
nothing on it is a recommendation to buy, sell or hold any asset. Risk scores, forecasts, alerts, scenarios and
other outputs are automated estimates built from third-party data and statistical models. They can be wrong,
incomplete or late. Make your own decisions and, where appropriate, consult a qualified professional.

## 2. How ChainIntel works and its limits

- **Third-party data.** Prices, liquidity, news, social posts, on-chain transfers and other data come from
  outside providers. We don't control them and can't guarantee they're accurate, complete or current.
- **Forecasts are probabilities.** The depeg forecast estimates how likely a coin is to move away from its
  peg. Its measured historical accuracy is shown on the Forecasts page; past performance doesn't guarantee
  future results, and the model will miss some events and raise some false alarms.
- **Alerts aren't guaranteed.** Alerts and emails depend on our servers, background jobs and third-party
  delivery services (email, Discord, Telegram). They may be delayed, filtered as spam, or not sent at all.
  Don't rely on ChainIntel as your only way of learning about market events.
- **Availability.** We may change, pause or discontinue any part of ChainIntel at any time, with or without
  notice.

## 3. Your account

- You must be at least 18 years old to create an account.
- Give a real email address you control, and keep your password private. You're responsible for activity
  under your account.
- One person per account. Tell us at {_contact_line()} if you think your account has been accessed without
  your permission.
- You can delete your account at any time from **Settings → Delete account**.

## 4. Acceptable use

You agree not to:

- try to access other users' accounts or data, or parts of ChainIntel you aren't authorized to use;
- interfere with or overload the service, including through automated scraping, bulk sign-ups or excessive
  requests;
- probe, scan or test the service's security without our written permission;
- use ChainIntel for anything unlawful, or to mislead others about the source or meaning of its data; or
- resell or redistribute ChainIntel's data or outputs in ways that break these terms or the terms of the
  underlying data providers.

We may suspend or close accounts that break these rules.

## 5. Third-party services and links

ChainIntel links to and relies on other services (for example data providers, block explorers, Reddit,
news sites, Discord and Telegram). Their content and practices are governed by their own terms, and we're not
responsible for them.

## 6. Disclaimer of warranties

ChainIntel is provided **"as is" and "as available"**, without warranties of any kind, express or implied,
including warranties of accuracy, reliability, fitness for a particular purpose, merchantability or
non-infringement, to the fullest extent the law allows.

## 7. Limitation of liability

To the fullest extent the law allows, ChainIntel and the people who run it won't be liable for any indirect,
incidental, special, consequential or punitive damages, or for any loss of profits, funds, data or trading
opportunities, arising from your use of (or inability to use) ChainIntel — including decisions made based on
its scores, forecasts or alerts, and alerts that were late or never arrived. Some places don't allow certain
limitations, so some of this may not apply to you.

## 8. Ending your use

You may stop using ChainIntel and delete your account at any time. We may suspend or end your access if you
break these terms or if we discontinue the service. Sections 1, 2, 6 and 7 continue to apply afterwards.

## 9. Changes to these terms

We may update these terms. We'll change the effective date above and, for significant changes, email
account holders with a confirmed address. Continuing to use ChainIntel after a change means you accept the
updated terms.

## 10. Contact

Questions about these terms: {_contact_line()}.
"""


def privacy_markdown() -> str:
    return f"""
# Privacy Policy

*Effective {EFFECTIVE_DATE}*

This policy explains what ChainIntel collects, why, who it's shared with, and the choices you have.
The short version: **we collect only what's needed to run your account and send you the alerts you ask for.
We don't sell your data, show ads, or use tracking or analytics cookies.**

## What we collect

**When you create an account**
- Username and email address.
- Your password, stored only as a salted one-way hash (scrypt). We can't see or recover your password.
- The date you created your account, your last sign-in, a count of recent failed sign-in attempts (used to
  lock out password-guessing), whether you've confirmed your email, and when you agreed to these policies.

**Settings you choose to save**
- Alert thresholds and whether alerts are on.
- Whether you want the daily digest.
- Notification channels you add: a Discord webhook URL and/or a Telegram chat ID.
- **Portfolio holdings** you enter on the Portfolio page (dollar amounts per stablecoin). These are used only
  to show you your own risk figures.

**Sign-in cookie**
- If you choose "Keep me signed in", your browser stores a cookie named `chainintel_session` containing a random
  token, for up to 30 days. We store only a hash of that token. Signing out deletes it. This is the only cookie
  ChainIntel sets; the hosting platform may use strictly necessary technical cookies of its own.

**One-time links**
- Password-reset and email-confirmation links contain random tokens, stored as hashes, that expire after
  1 hour (reset) or 3 days (confirmation) and are deleted once used.

**What we don't collect:** wallet addresses or connections, private keys, payment details, government IDs, or
your browsing activity elsewhere. Market data shown in the app (prices, liquidity, news) is fetched by our
servers and contains no information about you.

## How we use it

- To run your account, keep you signed in and protect it (for example, locking sign-in after repeated
  failed attempts).
- To send emails and alerts **you've turned on**: the daily digest, risk alerts, password resets and email
  confirmation.
- To show your own portfolio and alert settings back to you.

We don't use your data for advertising or profiling, and we don't sell or rent it.

## Who we share it with

Only the services needed to run ChainIntel:

- **Email provider** (currently Gmail/Google): your email address and the content of messages we send you.
- **Discord or Telegram**, only if you add them: alert messages are delivered through their services to the
  channel or chat you specify.
- **Hosting and database providers** that run the app and store its data.
- **Google Fonts**: your browser loads the site's typeface from Google, which receives your IP address.

We may also disclose information if required by law, or to protect the safety and security of ChainIntel and
its users.

## How long we keep it

- Account data and settings: until you delete your account.
- Sign-in sessions: up to 30 days, or until you sign out.
- Reset and confirmation links: until used or expired (1 hour / 3 days).
- Backups of the database, if any, may hold deleted data for a limited time until they're overwritten.

## Your choices and rights

- **Change your settings** — alerts, notification channels, digest and portfolio — in Settings and Portfolio.
- **Stop emails** — turn off the digest in Settings or use the unsubscribe link in any digest.
- **Sign out everywhere** — Settings → Security.
- **Delete your account** — Settings → Delete account permanently removes your account, settings,
  portfolio, sessions and alert history.
- **Get a copy of your data, or ask a question** — contact {_contact_line()}. Depending on where you live, you
  may have additional rights (such as access, correction or objection); we'll honor applicable requests.

## Security

Passwords and session tokens are stored only as hashes, sign-in is rate-limited, and the site should be served
over HTTPS when hosted. No system is perfectly secure, so please use a unique password.

## Children

ChainIntel isn't intended for anyone under 18, and we don't knowingly collect data from children. If you
believe a child has created an account, contact us and we'll delete it.

## Changes to this policy

We'll update the effective date above when this policy changes and, for significant changes, email account
holders with a confirmed address.

## Contact

Privacy questions or requests: {_contact_line()}.
"""


def render(kind: str):
    """Renders the Terms ("terms") or Privacy Policy ("privacy") in a readable column."""
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        st.markdown(terms_markdown() if kind == "terms" else privacy_markdown())
