from __future__ import annotations

from pathlib import Path


def load_project_env(env_file: Path) -> bool:
    """???? .env????????????"""
    if not env_file.exists():
        return False
    try:
        from dotenv import load_dotenv
    except Exception:
        return False
    return bool(load_dotenv(env_file, override=False))
