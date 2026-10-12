import config


def test_dotenv_parsing(tmp_path):
    p = tmp_path / ".env"
    p.write_text('# comment\nA=1\nexport B="two words"\nC=\'x=y\'\n\nbad line\n')
    assert config._read_dotenv(str(p)) == {"A": "1", "B": "two words", "C": "x=y"}


def test_environment_wins(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "from-env")
    assert config.get("ETHERSCAN_API_KEY") == "from-env"
    assert config.status()["ETHERSCAN_API_KEY"] is True
