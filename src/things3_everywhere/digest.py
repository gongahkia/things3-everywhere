"""Pure, deterministic formatting of structured Today results."""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import BridgeError

DEFAULT_TIMEZONE = "Asia/Singapore"


def local_day(now: datetime, timezone: str = DEFAULT_TIMEZONE) -> str:
    try:
        if (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
                or not isinstance(timezone, str) or not timezone):
            raise ValueError()
        return now.astimezone(ZoneInfo(timezone)).date().isoformat()
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise BridgeError("INVALID_TIMEZONE", "Use an IANA timezone and an aware datetime.") from None


def _title(value: str) -> str:
    # Keep titles intact, but render terminal controls visibly in local previews.
    return "".join(
        "\n  " if c == "\n" else f"\\u{ord(c):04x}" if ord(c) < 32 or 127 <= ord(c) <= 159 else c
        for c in value
    )


def format_digest(page: dict, *, now: datetime, timezone: str = DEFAULT_TIMEZONE) -> str:
    """No clock reads, Things access, notes, LLM, network, or calendar access."""
    if (type(page) is not dict or type(page.get("tasks")) is not list
            or type(page.get("has_more", False)) is not bool):
        raise BridgeError("INVALID_INPUT", "Digest input must be a structured task page.")
    lines = [f"Things Today — {local_day(now, timezone)} ({timezone})"]
    if page.get("has_more"):
        lines.append("PARTIAL LIST: the adapter limit was reached; open Things for the full list.")
    seen = set()
    omitted_deadlines = 0
    for task in page["tasks"]:
        if type(task) is not dict or not isinstance(task.get("id"), str) or not task["id"] or not isinstance(task.get("title"), str):
            raise BridgeError("INVALID_INPUT", "Digest tasks require stable IDs and titles.")
        try:
            task["title"].encode("utf-8")
        except UnicodeError:
            raise BridgeError("INVALID_INPUT", "Task titles must be valid Unicode.") from None
        if task["id"] in seen:
            continue
        seen.add(task["id"])
        deadline = task.get("deadline")
        reliable = False
        if isinstance(deadline, str):
            try:
                reliable = date.fromisoformat(deadline).isoformat() == deadline
            except ValueError:
                pass
        # Recurrence/template offsets cannot currently be established on the live adapter.
        reliable = reliable and task.get("recurrence") == "none"
        suffix = f" — deadline {deadline}" if reliable else ""
        if deadline is not None and not reliable:
            omitted_deadlines += 1
        lines.append("• " + _title(task["title"]) + suffix)
    if not seen:
        lines.append("No tasks in the Things Today list.")
    if omitted_deadlines:
        lines.append("Some deadline values omitted because their meaning could not be verified.")
    return "\n".join(lines)


def split_message(text: str, max_units: int = 4096) -> list[str]:
    """Bound UTF-16 units conservatively; never split a Unicode code point or drop text."""
    if not isinstance(text, str) or not text or type(max_units) is not int or not 2 <= max_units <= 4096:
        raise BridgeError("INVALID_INPUT", "Message must be nonempty Unicode within supported split limits.")
    try:
        text.encode("utf-8")
    except UnicodeError:
        raise BridgeError("INVALID_INPUT", "Message must be valid Unicode.") from None
    chunks, current, units = [], [], 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > max_units:
            chunks.append("".join(current))
            current, units = [], 0
        current.append(char)
        units += width
    if current:
        chunks.append("".join(current))
    return chunks
