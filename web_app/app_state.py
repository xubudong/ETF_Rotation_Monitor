from __future__ import annotations

import threading
from typing import Any

STATE_LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "payload": None,
    "source": None,
    "last_refresh": None,
    "last_error": None,
    "refreshing": False,
    "cache_updating": False,
    "cache_update_started": None,
    "cache_update_finished": None,
    "cache_update_last_error": None,
    "cache_update_result": None,
    "cache_update_progress": None,
    "tech_pool_updating": False,
    "tech_pool_update_started": None,
    "tech_pool_update_finished": None,
    "tech_pool_update_last_error": None,
    "tech_pool_update_result": None,
}


def current_state() -> dict[str, Any]:
    with STATE_LOCK:
        return dict(STATE)


def set_state(**updates: Any) -> None:
    with STATE_LOCK:
        STATE.update(updates)


def clear_payload() -> None:
    set_state(payload=None)
