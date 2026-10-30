"""The sole Things adapter. Uses the supported AppleScript interface only."""

from .errors import BridgeError
from .model import Page, Task
from .safety import WritePolicy
from .transport import AppleScriptTransport
from . import validation as v


def parse_task(row) -> Task:
    try:
        if type(row) is not list or len(row) != 6:
            raise ValueError()
        id, title, notes, status, tags, deadline = row
        v.task_id(id)
        if not isinstance(title, str) or not isinstance(notes, str):
            raise ValueError()
        if status not in {"open", "completed", "canceled"}:
            raise ValueError()
        if type(tags) is not list or any(not isinstance(t, str) for t in tags):
            raise ValueError()
        if deadline is not None:
            v.iso_date(deadline)
        return Task(id, title, notes, tags, deadline, status, "unknown")
    except (ValueError, TypeError, BridgeError):
        raise BridgeError("INVALID_RESPONSE", "Things returned an incomplete or invalid task record.") from None


class ThingsAppleScriptAdapter:
    def __init__(self, policy=WritePolicy(), *, transport=None, app_path=None):
        self.policy = policy
        self.transport = transport or AppleScriptTransport(policy, app_path=app_path)

    def _page(self, response, limit):
        rows = response.get("rows")
        if type(rows) is not list or type(response.get("has_more")) is not bool or len(rows) > limit:
            raise BridgeError("INVALID_RESPONSE", "Things returned an invalid task list.")
        return Page([parse_task(row) for row in rows], response["has_more"])

    def list_tasks(self, scope, limit=50):
        if scope not in {"Today", "Inbox"}:
            raise BridgeError("UNSUPPORTED_OPERATION", "Only Today and Inbox are exposed as lists.")
        limit = v.limit(limit)
        return self._page(self.transport.call(scope.lower(), {"limit": limit}), limit)

    def search(self, query, limit=50):
        query, limit = v.text(query, "query", 500, nonempty=True), v.limit(limit)
        return self._page(self.transport.call("search", {"query": query, "limit": limit}), limit)

    def get_task(self, id):
        id = v.task_id(id)
        result = parse_task(self.transport.call("get", {"id": id}).get("row"))
        if result.id != id:
            raise BridgeError("INVALID_RESPONSE", "Things returned a different task ID.")
        return result

    def get_handoff_task(self, id):
        id = v.task_id(id)
        response = self.transport.call("inspect_task", {"id": id})
        if response.get("kind") != "to do":
            raise BridgeError("ITEM_KIND_UNSUPPORTED", "Target is not a verified to-do item.")
        task = parse_task(response.get("row"))
        if task.id != id:
            raise BridgeError("INVALID_RESPONSE", "Things returned a different task ID.")
        return task

    def reveal_task(self, id):
        id = v.task_id(id)
        response = self.transport.call("show_task", {"id": id})
        if response.get("kind") != "to do" or response.get("id") != id:
            raise BridgeError("INVALID_RESPONSE", "Things returned an invalid reveal receipt.")
        return id

    def create_task(self, fields, *, execution="preview"):
        fields = v.fields(fields, create=True)
        self.policy.require(execution)
        response = self.transport.call("create", {"fields": fields, "execution": execution})
        try:
            return v.task_id(response.get("id"))
        except BridgeError:
            raise BridgeError("WRITE_UNVERIFIED", "Things accepted creation but returned no valid stable ID. "
                              "Inspect Things before any manual retry.", outcome="accepted_unverified") from None

    def update_task(self, id, fields, *, execution="preview"):
        v.task_id(id)
        v.fields(fields)
        self.policy.require(execution)
        self._reject_existing_mutation()

    def complete_task(self, id, *, execution="preview"):
        v.task_id(id)
        self.policy.require(execution)
        self._reject_existing_mutation()

    @staticmethod
    def _reject_existing_mutation():
        # No caller assertion, title heuristic, or in-memory "created by us" list
        # can establish the current recurrence state. There is no bypass flag.
        raise BridgeError("RECURRENCE_UNSAFE", "AppleScript recurrence detection is unverified. "
                          "Existing-task writes are blocked, including tasks created by this bridge.")

