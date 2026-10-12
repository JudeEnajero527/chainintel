# ChainIntel

Stablecoin risk monitoring: live peg, liquidity and news-sentiment scores for nine major stablecoins,
a 7-day depeg forecast, whale-transfer tracking, market/DeFi/yield views, and an optional daily email digest.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # optional: add API keys (see below)
streamlit run app.py        # or: python3 app.py
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
| `TELEGRAM_BOT_TOKEN` | Telegram push alerts (create a bot with @BotFather). |
| `DATABASE_URL` | Postgres for hosting (see below). Leave unset to use the local SQLite file. |

Keys can also be set as environment variables or in `.streamlit/secrets.toml`. **Settings → Data sources**
in the app shows which ones are connected.

## The depeg model

`python3 train_model.py` downloads daily prices for every USD stablecoin DefiLlama tracks (~230 coins, 2021→today)
and trains a gradient-boosted classifier for: *"this coin is on peg today — will it trade ≥1% off peg within
7 days?"* It is evaluated only on data after its training window, and the real metrics are written to
`chainintel_model_meta.json` and shown on the **Forecasts** page. Retrain occasionally to include recent history.

## Background collector

The collector keeps everything running when nobody has the app open. Every 5 minutes it assesses every coin
(and saves a snapshot the app reuses, so pages load instantly), records risk history, logs and scores the daily
forecasts (Forecasts → *Live track record*), sends push alerts, sends the daily digest at 8am, and retrains the
model once a month.

```bash
python3 collector.py --loop 300               # run in a terminal
bash deploy/install_collector_macos.sh        # or run it in the background on this Mac (starts at login)
bash deploy/install_collector_macos.sh uninstall
```

Log: `collector.log`. Options: `--digest-hour 8` (−1 to disable), `--retrain-days 30` (0 to disable).

## Alerts and the digest

Each user picks thresholds and channels (email, Discord webhook, Telegram) in **Settings**. A coin crossing its
threshold sends one alert, and one more when it recovers; a coin breaking its peg always alerts. Email goes only
to confirmed addresses.

```bash
python3 send_digest.py --dry-run   # preview the digest as digest_preview.html
python3 send_digest.py             # send it now (the collector also sends it daily)
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                           # unit tests, offline, throwaway database
pytest --postgres                # also against a temporary Postgres
RUN_NETWORK_TESTS=1 pytest       # also render every page against live data
```

GitHub Actions runs `pytest --postgres` on every push (`.github/workflows/tests.yml`).

## Hosting (Streamlit Community Cloud)

1. Create a free Postgres database (e.g. [Neon](https://neon.tech) or [Supabase](https://supabase.com)) and copy its
   connection string.
2. Push this repo to GitHub, then create an app at [share.streamlit.io](https://share.streamlit.io) with
   `app.py` as the entry point.
3. In the app's **Settings → Secrets**, paste `.streamlit/secrets.toml.example` filled in — at minimum
   `DATABASE_URL` and `CHAININTEL_URL`.
4. Add the same values as GitHub repository secrets. `.github/workflows/collector.yml` then runs the collector
   every 15 minutes against the hosted database, and `retrain.yml` retrains and commits the model monthly.

The app creates its tables on first run. SQLite isn't suitable there because the server's disk is wiped on restart.

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
| `db.py` | Connection layer: SQLite locally, Postgres when `DATABASE_URL` is set |
| `collector.py` | Background job: snapshots, history, forecasts, alerts, digest, retraining |
| `notify.py` | Push alerts (email, Discord, Telegram) |
| `mailer.py` | Outgoing email |
| `tests/` | pytest suite |

`chainintel.db` (SQLite) holds user accounts, risk history and the forecast log. It is git-ignored; back it up separately.

Not financial advice.
