from __future__ import annotations

import os

import pytest

from web_app.env_loader import load_project_env


def test_load_project_env_reads_file_without_overriding_existing_env(tmp_path, monkeypatch):
    pytest.importorskip("dotenv")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AKSHARE_PROXY_TOKEN=file-token\nWEB_HOST=0.0.0.0\nWEB_PORT=9000\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AKSHARE_PROXY_TOKEN", "system-token")
    monkeypatch.delenv("WEB_HOST", raising=False)
    monkeypatch.delenv("WEB_PORT", raising=False)

    assert load_project_env(env_file) is True
    assert os.environ["AKSHARE_PROXY_TOKEN"] == "system-token"
    assert os.environ["WEB_HOST"] == "0.0.0.0"
    assert os.environ["WEB_PORT"] == "9000"


def test_load_project_env_missing_file_is_noop(tmp_path):
    assert load_project_env(tmp_path / ".env") is False
