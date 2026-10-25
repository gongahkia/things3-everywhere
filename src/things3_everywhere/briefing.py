"""Digest orchestration reusing the existing Things service."""

from datetime import datetime, timezone
import os

from .digest import DEFAULT_TIMEZONE, format_digest, local_day
from .runtime import live_service
from .telegram import send_once
from .validation import MAX_RESULTS


def read_only_service():
    # Digest operations never inherit a write opt-in from an unrelated shell.
    return live_service(read_only=True)


def synthetic_page():
    # An explicit demo payload, not a competing adapter or replacement store.
    return {"tasks": [
        {"id": "synthetic-1", "title": "Shortcut Test", "deadline": "2030-04-05", "recurrence": "none"},
        {"id": "synthetic-2", "title": "Read a chapter 📚", "deadline": None, "recurrence": "none"},
    ], "has_more": False}


def briefing(*, action="preview", fake=False, execute=False, zone=None, env=None,
             service_factory=read_only_service, sender=send_once, now=None):
    from .errors import BridgeError
    if type(fake) is not bool or type(execute) is not bool or action not in ("preview", "send-once") or (action == "preview" and execute):
        raise BridgeError("INVALID_INPUT", "Preview cannot execute a send.")
    env = os.environ if env is None else env
    selected_zone = zone if zone is not None else env.get("BRIEFING_TIMEZONE", DEFAULT_TIMEZONE)
    instant = now if now is not None else datetime.now(timezone.utc)
    local_day(instant, selected_zone)  # Reject invalid options before touching Things.
    page = synthetic_page() if fake else service_factory().today(limit=MAX_RESULTS, include_notes=False)
    text = format_digest(page, now=instant, timezone=selected_zone)
    source = "synthetic" if fake else "live_things"
    if action == "preview":
        return {"source": source, "outcome": "local_preview", "requests": 0, "text": text}
    return {"source": source, **sender(text, execute=execute, env=env)}
