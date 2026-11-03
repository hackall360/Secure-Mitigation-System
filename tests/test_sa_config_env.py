"""F-205/F-219: .env reaches sms_cli env path; config/docs drift guards."""

from pathlib import Path

import pytest

import sms_cli
from library.core import config as cfg

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for name in [*sms_cli.ENV_FALLBACKS.values(), "PURPLEBOX_DOCKER_TIMEOUT_SECONDS"]:
        # setenv first so undo removes anything load_dotenv_file() writes.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_env(path: Path, text: str) -> None:
    env = path / ".env"
    env.write_text(text)
    env.chmod(0o600)


def test_env_values_reads_dotenv(clean_env, monkeypatch):
    _write_env(clean_env, "PURPLEBOX_RESEARCH=on\n")
    out = sms_cli._env_values()
    assert out.get("research") is True


def test_exported_env_wins_over_dotenv(clean_env, monkeypatch):
    _write_env(clean_env, "PURPLEBOX_RESEARCH=on\n")
    monkeypatch.setenv("PURPLEBOX_RESEARCH", "off")
    assert "research" not in sms_cli._env_values()


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("research", "on", True),
        ("research_scanners", "trivy", "trivy"),
        ("intel_offline", "1", True),
    ],
)
def test_every_env_fallback_is_honored(clean_env, monkeypatch, key, value, expected):
    assert set(sms_cli.ENV_FALLBACKS) == {"research", "research_scanners", "intel_offline"}
    monkeypatch.setenv(sms_cli.ENV_FALLBACKS[key], value)
    assert sms_cli._env_values()[key] == expected


def test_docker_timeout_env_is_read(clean_env, monkeypatch):
    monkeypatch.setenv("PURPLEBOX_DOCKER_TIMEOUT_SECONDS", "45")
    assert cfg.load_config().docker_timeout_seconds == 45


def test_docker_timeout_zero_rejected(clean_env, monkeypatch):
    monkeypatch.setenv("PURPLEBOX_DOCKER_TIMEOUT_SECONDS", "0")
    with pytest.raises(cfg.ConfigurationError):
        cfg.load_config()


@pytest.mark.parametrize(
    "name",
    [
        "PURPLEBOX_DTRACK_URL",
        "PURPLEBOX_DTRACK_API_KEY",
        "NVD_API_KEY",
        "PURPLEBOX_VAULT_DIR",
        "PURPLEBOX_INTEL_OFFLINE",
        "PURPLEBOX_LOG_RAW_RESPONSES",
        "PURPLEBOX_DOCKER_TIMEOUT_SECONDS",
    ],
)
def test_example_env_documents_knob(name):
    text = (ROOT / "example.env").read_text()
    assert f"# {name}=" in text


def test_cli_doc_documents_config_precedence():
    text = (ROOT / "docs/reference/CLI.md").read_text()
    assert "flag > config file > env > default" in text
