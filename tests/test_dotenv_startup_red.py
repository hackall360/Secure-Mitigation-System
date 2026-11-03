# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED-first: startup must load owner-only .env (stdlib only).

`load_config()` reads os.environ only, so a plain `python main.py --serve`
with the key sitting in `.env` reports api_key_configured=false and the
WebUI disables Launch. The loader below parses KEY=value lines (stdlib,
no dependency) and fills only vars the process env does not already set.
Every pin below FAILS before the loader is wired into load_config.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "library" / "core" / "config.py"
SOURCE = CONFIG.read_text(encoding="utf-8")


def test_loader_function_exists():
    assert "def load_dotenv" in SOURCE or "def _load_dotenv" in SOURCE, (
        "config.py must define a stdlib .env loader"
    )


def test_load_config_calls_loader_first():
    body = SOURCE.split("def load_config", 1)[1].split("\ndef ", 1)[0]
    assert "dotenv" in body.lower(), (
        "load_config() must invoke the .env loader before reading os.getenv"
    )


def test_loader_does_not_override_process_env(monkeypatch, tmp_path):
    """Real env wins: loader must never clobber an exported var."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("SMS_PROBE_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("SMS_PROBE_KEY", "from-process")
    sys.path.insert(0, str(ROOT))
    try:
        from library.core.config import load_dotenv_file

        load_dotenv_file(dotenv)
        assert os.environ["SMS_PROBE_KEY"] == "from-process"
    finally:
        sys.path.remove(str(ROOT))
        del os.environ["SMS_PROBE_KEY"]


def test_loader_fills_missing_var_from_file(monkeypatch, tmp_path):
    """Missing var is filled from .env so serve picks up the key."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("SMS_PROBE_KEY2=from-file\n", encoding="utf-8")
    monkeypatch.delenv("SMS_PROBE_KEY2", raising=False)
    sys.path.insert(0, str(ROOT))
    try:
        from library.core.config import load_dotenv_file

        load_dotenv_file(dotenv)
        assert os.environ["SMS_PROBE_KEY2"] == "from-file"
    finally:
        sys.path.remove(str(ROOT))
        del os.environ["SMS_PROBE_KEY2"]


def test_loader_skips_comments_and_blank_lines(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("# a comment\n\nSMS_PROBE_KEY3 = spaced-value  \n", encoding="utf-8")
    monkeypatch.delenv("SMS_PROBE_KEY3", raising=False)
    sys.path.insert(0, str(ROOT))
    try:
        from library.core.config import load_dotenv_file

        load_dotenv_file(dotenv)
        assert os.environ["SMS_PROBE_KEY3"] == "spaced-value"
    finally:
        sys.path.remove(str(ROOT))
        del os.environ["SMS_PROBE_KEY3"]


def test_loader_missing_file_is_noop(tmp_path):
    """No .env on disk: loader returns quietly, nothing raises."""
    sys.path.insert(0, str(ROOT))
    try:
        from library.core.config import load_dotenv_file

        load_dotenv_file(tmp_path / ".env-absent")
    finally:
        sys.path.remove(str(ROOT))


def test_keyed_config_reads_key_from_dotenv_file(monkeypatch, tmp_path):
    """End to end: key in .env file (not exported) reaches load_config()."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("META_MUSE_API_KEY=file-key-123\n", encoding="utf-8")
    monkeypatch.delenv("META_MUSE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    for mod in [m for m in list(sys.modules) if m.startswith("library.core.config")]:
        del sys.modules[mod]
    sys.path.insert(0, str(ROOT))
    try:
        from library.core import config as cfg

        loaded = cfg.load_config()
        assert loaded.meta_api_key == "file-key-123"
    finally:
        sys.path.remove(str(ROOT))
        for mod in [m for m in list(sys.modules) if m.startswith("library.core.config")]:
            del sys.modules[mod]


def test_no_third_party_dotenv_dependency():
    reqs = list(ROOT.glob("requirements*.txt")) + [ROOT / "pyproject.toml"]
    text = "\n".join(p.read_text(encoding="utf-8") for p in reqs if p.is_file())
    assert "dotenv" not in text.lower().replace("load_dotenv", "").replace("load-dotenv", ""), (
        "loader must stay stdlib-only"
    )
