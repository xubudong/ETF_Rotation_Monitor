from __future__ import annotations

import pytest

from web_app import cache_update


def test_cache_update_requires_proxy_token(monkeypatch):
    monkeypatch.setattr(cache_update, "AKSHARE_PROXY_TOKEN", "")
    with pytest.raises(RuntimeError, match="AKSHARE_PROXY_TOKEN"):
        cache_update.install_akshare_proxy_patch()
