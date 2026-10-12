# ChainIntel

Stablecoin risk monitoring: live peg, liquidity and news-sentiment scores for nine major stablecoins,
a 7-day depeg forecast, whale-transfer tracking, market/DeFi/yield views, and an optional daily email digest.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # optional: add API keys (see below)
streamlit run app.py
```

The first page load takes ~20 seconds while the FinBERT sentiment model downloads/loads; after that,
everything is cached.

## Optional keys (`.env`)

| Key | Unlocks |
|---|---|
| `ETHERSCAN_API_KEY` | Whale alerts and gas prices. Free at [etherscan.io/apis](https://etherscan.io/apis). |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | Reliable Reddit data (official API). Create a "script" app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps). Without these, the rate-limited public feed is used. |
| `CHAININTEL_EMAIL`, `CHAININTEL_APP_PASS` | Sending the daily digest (Gmail + [App Password](https://myaccount.google.com/apppasswords)). |
| `CHAININTEL_URL` | Public dashboard URL used in email links (default `http://localhost:8501`). |

Keys can also be set as environment variables or in `.streamlit/secrets.toml`. **Settings → Data sources**
in the app shows which ones are connected.

## The depeg model

`python3 train_model.py` downloads daily prices for every USD stablecoin DefiLlama tracks (~230 coins, 2021→today)
and trains a gradient-boosted classifier for: *"this coin is on peg today — will it trade ≥1% off peg within
7 days?"* It is evaluated only on data after its training window, and the real metrics are written to
`chainintel_model_meta.json` and shown on the **Forecasts** page. Retrain occasionally to include recent history.

## Daily digest

```bash
python3 send_digest.py --dry-run   # writes digest_preview.html
python3 send_digest.py             # sends to every user who opted in
```

Cron example: `0 8 * * * cd /path/to/chainintel2 && /usr/bin/python3 send_digest.py >> digest.log 2>&1`

## Layout

| Path | What it is |
|---|---|
| `app.py` | Entry point: theme, sign-in, navigation, sidebar |
| `views/` | One file per page |
| `chainintel_core.py` | Data fetching (cached), risk scoring, model inference |
| `depeg_model.py` | Feature/label code shared by training and live inference |
| `auth.py` | Accounts, scrypt passwords, remember-me sessions, per-user preferences |
| `styles.py` | Design tokens, CSS, Plotly template, formatting helpers |
| `config.py` | Settings loader (env → `.env` → `secrets.toml`) |

`chainintel.db` (SQLite) holds user accounts and recorded risk history. It is git-ignored; back it up separately.

Not financial advice.
