"""Reusable task operations for MCP, CLI and future interfaces."""

from threading import RLock

from .errors import BridgeError
from .model import Adapter, Task
from .safety import WritePolicy, require_nonrepeating
from . import validation as v


class ThingsService:
    def __init__(self, adapter: Adapter, policy: WritePolicy = WritePolicy()):
        self.adapter = adapter
        self.policy = policy
        self._writes = RLock()

    def _page(self, page, limit: int, include_notes: bool) -> dict:
        return {"tasks": [t.public(include_notes=include_notes) for t in page.tasks[:limit]],
                "count": min(len(page.tasks), limit), "limit": limit,
                "has_more": page.has_more or len(page.tasks) > limit}

    def today(self, limit=50, include_notes=False):
        limit = v.limit(limit)
        v.boolean(include_notes, "include_notes")
        return self._page(self.adapter.list_tasks("Today", limit), limit, include_notes)

    def inbox(self, limit=50, include_notes=False):
        limit = v.limit(limit)
        v.boolean(include_notes, "include_notes")
        return self._page(self.adapter.list_tasks("Inbox", limit), limit, include_notes)

    def search(self, query, limit=50, include_notes=False):
        query = v.text(query, "query", 500, nonempty=True)
        limit = v.limit(limit)
        v.boolean(include_notes, "include_notes")
        return self._page(self.adapter.search(query, limit), limit, include_notes)

    def get_task(self, id):
        return {"task": self._get(v.task_id(id)).public()}

    def _get(self, id) -> Task:
        task = self.adapter.get_task(id)
        if task is None:
            raise BridgeError("NOT_FOUND", "No task exists with that stable ID.")
        if task.id != id:
            raise BridgeError("INVALID_RESPONSE", "Things returned a different task ID.")
        return task

    def _preview(self, operation, fields, task=None):
        blockers = []
        if not self.policy.enabled:
            blockers.append("READ_ONLY")
        if task is not None and task.recurrence != "none":
            blockers.append("RECURRENCE_UNSAFE")
        return {"outcome": "preview", "operation": operation,
                "id": task.id if task else None, "fields": fields,
                "semantics": "Supplied fields replace values; omitted fields remain unchanged.",
                "execution_blockers": blockers, "mutated": False}

    def create_task(self, fields, execution="preview"):
        fields = v.fields(fields, create=True)
        v.execution(execution)
        if execution == "preview":
            return self._preview("create", fields)
        self.policy.require(execution)
        with self._writes:
            expected = {"notes": "", "tags": [], "deadline": None, "status": "open", **fields}
            return self._write_and_verify(
                lambda: self.adapter.create_task(fields, execution=execution), expected)

    def update_task(self, id, fields, execution="preview"):
        id, fields = v.task_id(id), v.fields(fields)
        v.execution(execution)
        if execution == "execute":
            self.policy.require(execution)
        with self._writes:
            task = self._get(id)
            if execution == "preview":
                return self._preview("update", fields, task)
            require_nonrepeating(task)
            expected = {**task.public(), **fields}
            return self._write_and_verify(
                lambda: self.adapter.update_task(id, fields, execution=execution), expected, id)

    def complete_task(self, id, execution="preview"):
        id = v.task_id(id)
        v.execution(execution)
        if execution == "execute":
            self.policy.require(execution)
        with self._writes:
            task = self._get(id)
            if execution == "preview":
                return self._preview("complete", {"status": "completed"}, task)
            require_nonrepeating(task)
            expected = {**task.public(), "status": "completed"}
            return self._write_and_verify(
                lambda: self.adapter.complete_task(id, execution=execution), expected, id)

    def _write_and_verify(self, write, expected, target_id=None):
        # Exactly one dispatch. A timeout or malformed receipt must never cause retry.
        try:
            affected_id = write()
        except BridgeError:
            raise
        except Exception:
            raise BridgeError("WRITE_UNCERTAIN", "The write outcome is unknown. Inspect Things "
                              "before any manual retry.", outcome="unknown") from None
        try:
            v.task_id(affected_id)
            if target_id is not None and affected_id != target_id:
                raise ValueError()
            actual = self._get(affected_id)
            for key, value in expected.items():
                observed = getattr(actual, key)
                if key == "tags":
                    if set(observed) != set(value):
                        raise ValueError()
                elif observed != value:
                    raise ValueError()
        except Exception:
            raise BridgeError("WRITE_UNVERIFIED", "Things accepted the request, but the resulting "
                              "state could not be verified. Inspect Things before any manual retry.",
                              outcome="accepted_unverified") from None
        return {"outcome": "verified", "id": affected_id, "task": actual.public(),
                "retry_safe": False}
