"""
Settings and secrets, in one place.

Each key is looked up in this order (first hit wins):
  1. a real environment variable            ETHERSCAN_API_KEY=… streamlit run app.py
  2. the project's .env file                 copy .env.example to .env and fill it in
  3. .streamlit/secrets.toml                 what Streamlit Community Cloud uses

Works without Streamlit running, so send_digest.py and train_model.py read the same values.
"""
import os
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))

KEYS = {
    "ETHERSCAN_API_KEY":    "Whale alerts + gas prices — free key at etherscan.io/apis",
    "REDDIT_CLIENT_ID":     "Reddit app id — create a 'script' app at reddit.com/prefs/apps",
    "REDDIT_CLIENT_SECRET": "Reddit app secret",
    "CHAININTEL_EMAIL":     "Gmail address the daily digest is sent from",
    "CHAININTEL_APP_PASS":  "Gmail App Password (myaccount.google.com/apppasswords)",
    "CHAININTEL_URL":       "Public URL of the dashboard, used in email links",
    "CHAININTEL_CONTACT_EMAIL": "Public contact address shown in the Terms of Use and Privacy Policy",
    "CHAININTEL_DB":        "Path to the SQLite database (default: chainintel.db next to the code)",
    "DATABASE_URL":         "Postgres connection string for hosting (overrides CHAININTEL_DB)",
    "TELEGRAM_BOT_TOKEN":   "Telegram bot token for push alerts (@BotFather)",
    "SMTP_HOST":            "SMTP server (default smtp.gmail.com)",
    "SMTP_PORT":            "SMTP port (default 587)",
}


def _read_dotenv(path):
    values = {}
    if not os.path.exists(path):
        return values
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            values[key.strip().removeprefix("export ").strip()] = val
    return values


def _read_secrets(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return {k: str(v) for k, v in data.items() if not isinstance(v, dict)}


_DOTENV = _read_dotenv(os.path.join(HERE, ".env"))
_SECRETS = _read_secrets(os.path.join(HERE, ".streamlit", "secrets.toml"))


def get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _DOTENV.get(key) or _SECRETS.get(key) or default


def status() -> dict:
    """{key: True/False} — whether each optional setting is configured (never exposes values)."""
    return {k: bool(get(k)) for k in KEYS}
