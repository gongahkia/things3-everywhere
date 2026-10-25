"""One validation contract shared by CLI, MCP, service and adapter."""

from datetime import date
import re

from .errors import BridgeError

MAX_RESULTS = 100
DEFAULT_LIMIT = 50
WRITABLE_FIELDS = frozenset({"title", "notes", "tags", "deadline"})


def invalid(message: str):
    raise BridgeError("INVALID_INPUT", message)


def text(value, field: str, maximum: int, *, nonempty=False) -> str:
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        invalid(f"{field} must be text within its documented size limit, without NUL.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        invalid(f"{field} must contain valid Unicode.")
    if nonempty and not value.strip():
        invalid(f"{field} must not be blank.")
    return value


def task_id(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value):
        invalid("id must be one stable Things ID (1–128 ASCII letters, digits, '.', '_' or '-').")
    return value


def limit(value=DEFAULT_LIMIT) -> int:
    if type(value) is not int or not 1 <= value <= MAX_RESULTS:
        invalid(f"limit must be an integer from 1 to {MAX_RESULTS}.")
    return value


def boolean(value, field: str) -> bool:
    if type(value) is not bool:
        invalid(f"{field} must be a boolean.")
    return value


def execution(value="preview") -> str:
    if value not in ("preview", "execute"):
        invalid("execution must be 'preview' or 'execute'.")
    return value


def iso_date(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value, re.ASCII):
        invalid("deadline must be a calendar date in YYYY-MM-DD format.")
    try:
        date.fromisoformat(value)
    except ValueError:
        invalid("deadline must be a valid calendar date.")
    return value


def fields(value, *, create=False) -> dict:
    if type(value) is not dict:
        invalid("fields must be an object.")
    if set(value) - WRITABLE_FIELDS:
        raise BridgeError("UNSUPPORTED_FIELD", "Supported fields: title, notes, tags, deadline. "
                          "start_date, recurrence and other fields are not supported.")
    if not value or (create and "title" not in value):
        invalid("Creation requires title; an update requires at least one supplied field.")
    result = {}
    for key, val in value.items():
        if key == "title":
            result[key] = text(val, "title", 500, nonempty=True)
        elif key == "notes":
            result[key] = text(val, "notes", 20_000)
        elif key == "tags":
            if type(val) is not list or len(val) > 25:
                invalid("tags must be an array with at most 25 distinct existing tag names.")
            tags = [text(t, "tag", 80, nonempty=True) for t in val]
            if any(t != t.strip() or "," in t or "\n" in t or "\r" in t for t in tags):
                invalid("Tag names cannot contain commas, newlines or surrounding whitespace.")
            if len(set(tags)) != len(tags):
                invalid("tags must not contain duplicates.")
            result[key] = tags
        else:
            if val is None:
                raise BridgeError("UNSUPPORTED_FIELD", "Deadline clearing is not verified for "
                                  "this AppleScript adapter. Omit deadline to preserve it.")
            result[key] = iso_date(val)
    return result

