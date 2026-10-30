"""Narrow MCP definitions and dispatch; no task-editing logic lives here."""

from jsonschema import Draft202012Validator

from .errors import BridgeError, unexpected_error
from . import validation as v


def object_schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


LIST = {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        "include_notes": {"type": "boolean", "default": False}}
ID = {"type": "string", "pattern": "^[A-Za-z0-9._-]{1,128}$",
      "description": "Stable Things ID from a read tool; never a title."}
EXECUTION = {"type": "string", "enum": ["preview", "execute"], "default": "preview",
             "description": "Preview never mutates. Execute also requires THINGS_ALLOW_WRITES=true."}
FIELDS = object_schema({
    "title": {"type": "string", "minLength": 1, "maxLength": 500},
    "notes": {"type": "string", "maxLength": 20000, "description": "Replace notes; empty string clears. No append mode."},
    "tags": {"type": "array", "maxItems": 25, "uniqueItems": True,
             "items": {"type": "string", "minLength": 1, "maxLength": 80},
             "description": "Replace with existing tag names; [] clears. No merge mode."},
    "deadline": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
                 "description": "Local calendar deadline, not start date. Clearing is unsupported."},
})
FIELDS["minProperties"] = 1
CREATE_FIELDS = {**FIELDS, "required": ["title"]}


def definition(name, description, schema, *, writing=False):
    return {"name": name, "description": description, "inputSchema": schema,
            "annotations": {"readOnlyHint": not writing, "destructiveHint": writing,
                            "idempotentHint": not writing, "openWorldHint": False}}


TOOL_DEFINITIONS = [
    definition("things_today", "Read the actual Things Today list. Up to 100 tasks; has_more flags truncation.", object_schema(LIST)),
    definition("things_inbox", "Read Things Inbox. Up to 100 tasks; has_more flags truncation.", object_schema(LIST)),
    definition("things_search", "Search open task titles using Things AppleScript contains semantics. Does not search notes or Logbook; at most 100 results.",
               object_schema({**LIST, "query": {"type": "string", "minLength": 1, "maxLength": 500}}, ["query"])),
    definition("things_get_task", "Retrieve one task, including notes, by its stable Things ID.", object_schema({"id": ID}, ["id"])),
    definition("things_create_task", "Preview or create one nonrepeating task in Inbox. Title required; start_date unsupported. Execute requires global opt-in and read-back verification. Never retry an uncertain write automatically.",
               object_schema({"fields": CREATE_FIELDS, "execution": EXECUTION}, ["fields"]), writing=True),
    definition("things_update_task", "Preview replacement of supplied fields of one stable ID. Omitted fields stay unchanged. Live execution is currently blocked: AppleScript recurrence safety is unknown.",
               object_schema({"id": ID, "fields": FIELDS, "execution": EXECUTION}, ["id", "fields"]), writing=True),
    definition("things_complete_task", "Preview completion of one stable ID. Live execution is currently blocked: AppleScript recurrence safety is unknown.",
               object_schema({"id": ID, "execution": EXECUTION}, ["id"]), writing=True),
]
SESSION = {"session_id": {"type": "string", "pattern": "^[A-Za-z0-9._-]{1,128}$"}}
TOOL_DEFINITIONS.extend([
    definition("things_prepare_manual_change", "Prepare one human edit. Reads only; never reveals or edits. Snapshot lasts 15 minutes in this server process. Recurrence remains unknown.",
               object_schema({"id": ID, "operation": {"enum": ["rename", "replace_notes", "change_deadline", "complete"]},
                              "value": {"type": "string"}}, ["id", "operation"])),
    definition("things_reveal_manual_change", "Explicit user-invoked UI reveal for a prepared handoff. Require user approval before calling. No task mutation. One reveal attempt; never retry automatically.",
               object_schema(SESSION, ["session_id"])),
    definition("things_verify_manual_change", "After the user edits manually, compare the same ID with the private snapshot. Consumes the session even on failure. Never edits or infers success from reveal.",
               object_schema(SESSION, ["session_id"])),
])
for tool in TOOL_DEFINITIONS[-3:]:
    tool["annotations"]["idempotentHint"] = False

METHODS = {"things_today": "today", "things_inbox": "inbox", "things_search": "search",
           "things_get_task": "get_task", "things_create_task": "create_task",
           "things_update_task": "update_task", "things_complete_task": "complete_task"}
METHODS.update({"things_prepare_manual_change": "prepare_manual_change",
                "things_reveal_manual_change": "reveal_manual_change",
                "things_verify_manual_change": "verify_manual_change"})
VALIDATORS = {d["name"]: Draft202012Validator(d["inputSchema"]) for d in TOOL_DEFINITIONS}


def dispatch(service, name, arguments):
    """Return (structured body, is_error) for either MCP or CLI. Never echo exceptions."""
    try:
        if name not in METHODS:
            raise BridgeError("UNKNOWN_TOOL", "This tool is not exposed by Things3 Everywhere.")
        if type(arguments) is not dict:
            raise BridgeError("INVALID_INPUT", "Tool arguments must be an object.")
        if name in {"things_create_task", "things_update_task"} and "fields" in arguments:
            v.fields(arguments["fields"], create=name == "things_create_task")
        if not VALIDATORS[name].is_valid(arguments):
            raise BridgeError("INVALID_INPUT", "Arguments do not match the tool schema; unknown arguments are rejected.")
        return getattr(service, METHODS[name])(**arguments), False
    except BridgeError as error:
        return {"error": error.public()}, True
    except Exception:
        return {"error": unexpected_error().public()}, True

