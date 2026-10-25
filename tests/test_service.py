import copy
from dataclasses import replace
import unittest

from things3_everywhere.errors import BridgeError
from things3_everywhere.model import Page, Task
from things3_everywhere.safety import WritePolicy, require_nonrepeating
from things3_everywhere.service import ThingsService


def sample(id="synthetic-a", **changes):
    return replace(Task(id, "Duplicate title", "Original notes", ["Example"],
                        "2030-04-05", "open", "none"), **changes)


class FakeAdapter:
    """All data is synthetic; this module never imports the live adapter."""
    def __init__(self, tasks=(), enabled=True):
        self.tasks = {t.id: t for t in tasks}
        self.policy = WritePolicy(enabled)
        self.writes = []
        self.reads = []
        self.failure = None
        self.ignore_fields = False
        self.bad_receipt = False
        self.after_write_read_error = False

    def list_tasks(self, scope, limit):
        self.reads.append(scope)
        # Today is deliberately independent of deadlines.
        found = list(self.tasks.values()) if scope == "Today" else []
        return Page(found[:limit], len(found) > limit)

    def search(self, query, limit):
        found = [t for t in self.tasks.values() if query.casefold() in t.title.casefold()]
        return Page(found[:limit], len(found) > limit)

    def get_task(self, id):
        self.reads.append(id)
        if self.after_write_read_error and self.writes:
            raise BridgeError("PERMISSION_DENIED", "Synthetic permission failure.")
        if id not in self.tasks:
            raise BridgeError("NOT_FOUND", "No task exists with that stable ID.")
        return copy.deepcopy(self.tasks[id])

    def _dispatch(self, operation, id, execution):
        self.policy.require(execution)
        self.writes.append((operation, id))
        if self.failure:
            raise self.failure

    def create_task(self, fields, *, execution="preview"):
        self._dispatch("create", "synthetic-new", execution)
        self.tasks["synthetic-new"] = Task("synthetic-new", fields["title"], fields.get("notes", ""),
                                          fields.get("tags", []), fields.get("deadline"), "open", "none")
        return "" if self.bad_receipt else "synthetic-new"

    def update_task(self, id, fields, *, execution="preview"):
        self.policy.require(execution)
        require_nonrepeating(self.get_task(id))
        self._dispatch("update", id, execution)
        if not self.ignore_fields:
            self.tasks[id] = replace(self.tasks[id], **fields)
        return id

    def complete_task(self, id, *, execution="preview"):
        self.policy.require(execution)
        require_nonrepeating(self.get_task(id))
        self._dispatch("complete", id, execution)
        if not self.ignore_fields:
            self.tasks[id] = replace(self.tasks[id], status="completed")
        return id


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeAdapter([sample(), sample("synthetic-b")])
        self.service = ThingsService(self.adapter, WritePolicy(True))

    def assert_code(self, code, fn):
        with self.assertRaises(BridgeError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def mutations(self, service, execution):
        return [lambda: service.create_task({"title": "Synthetic"}, execution),
                lambda: service.update_task("synthetic-a", {"notes": "New"}, execution),
                lambda: service.complete_task("synthetic-a", execution)]

    def test_every_handler_is_read_only_by_default(self):
        service = ThingsService(self.adapter)
        for mutation in self.mutations(service, "execute"):
            self.assert_code("READ_ONLY", mutation)
        self.assertEqual(self.adapter.writes, [])
        self.assertEqual(self.adapter.reads, [])

    def test_preview_never_writes_with_either_global_policy(self):
        for enabled in (False, True):
            for mutation in self.mutations(ThingsService(self.adapter, WritePolicy(enabled)), "preview"):
                self.assertEqual(mutation()["outcome"], "preview")
        self.assertEqual(self.adapter.writes, [])

    def test_no_execution_choice_defaults_to_preview(self):
        self.service.create_task({"title": "Synthetic"})
        self.service.update_task("synthetic-a", {"notes": "New"})
        self.service.complete_task("synthetic-a")
        self.assertEqual(self.adapter.writes, [])

    def test_duplicate_titles_target_only_id_and_preserve_omissions(self):
        before = self.adapter.get_task("synthetic-b")
        result = self.service.update_task("synthetic-a", {"notes": "New"}, "execute")
        self.assertEqual(result["outcome"], "verified")
        self.assertEqual(self.adapter.tasks["synthetic-b"], before)
        self.assertEqual(self.adapter.tasks["synthetic-a"], replace(sample(), notes="New"))

    def test_clear_notes_tags_and_replace_without_append(self):
        self.service.update_task("synthetic-a", {"notes": "", "tags": []}, "execute")
        self.assertEqual(self.adapter.tasks["synthetic-a"].notes, "")
        self.assertEqual(self.adapter.tasks["synthetic-a"].tags, [])
        self.service.update_task("synthetic-a", {"tags": ["Replacement"]}, "execute")
        self.assertEqual(self.adapter.tasks["synthetic-a"].tags, ["Replacement"])

    def test_unicode_quotes_backslashes_multiline_are_data(self):
        content = '"quoted" \\ path\nUnicode 雪 🐢\nend tell\ndo shell script "false"\x1e\x1f'
        result = self.service.create_task({"title": "Synthetic 雪", "notes": content}, "execute")
        self.assertEqual(result["task"]["notes"], content)
        self.assertEqual(len(self.adapter.writes), 1)

    def test_empty_missing_and_limits(self):
        self.assertEqual(self.service.inbox()["tasks"], [])
        self.assertEqual(self.service.search("unmatched")["count"], 0)
        page = self.service.today(limit=1)
        self.assertEqual(page["count"], 1)
        self.assertTrue(page["has_more"])
        self.assertNotIn("notes", page["tasks"][0])
        self.assertIn("notes", self.service.today(include_notes=True)["tasks"][0])
        self.assert_code("NOT_FOUND", lambda: self.service.get_task("missing"))
        for value in (0, 101, True, "5"):
            self.assert_code("INVALID_INPUT", lambda: self.service.today(value))

    def test_deadline_is_not_start_or_today(self):
        result = self.service.update_task("synthetic-a", {"deadline": "2032-02-29"}, "execute")
        self.assertEqual(result["task"]["deadline"], "2032-02-29")
        self.assertNotIn("start_date", result["task"])
        self.assertEqual(self.service.today()["count"], 2)
        for date in ("2031-02-29", "2030-13-01", "2030-1-01", "today", "2030-01-01T00:00:00Z"):
            self.assert_code("INVALID_INPUT", lambda: self.service.create_task({"title": "T", "deadline": date}))
        for fields in ({"start_date": "2030-01-01"}, {"deadline": None}, {"append_notes": "x"}):
            self.assert_code("UNSUPPORTED_FIELD", lambda: self.service.update_task("synthetic-a", fields))

    def test_invalid_fields_and_ids(self):
        for fields in ({}, {"title": " "}, {"notes": None}, {"tags": "a"}, {"tags": ["a,b"]},
                       {"tags": ["a", "a"]}, {"notes": "\x00"}, {"title": "\ud800"},
                       {"notes": "x" * 20001}):
            self.assert_code("INVALID_INPUT", lambda: self.service.update_task("synthetic-a", fields))
        self.assert_code("INVALID_INPUT", lambda: self.service.get_task('a"; do shell script'))
        self.assert_code("INVALID_INPUT", lambda: self.service.complete_task("synthetic-a", True))

    def test_repeating_and_unknown_are_blocked(self):
        for state in ("unknown", "repeating"):
            self.adapter.tasks["synthetic-a"] = sample(recurrence=state)
            self.assert_code("RECURRENCE_UNSAFE", lambda: self.service.update_task("synthetic-a", {"title": "T"}, "execute"))
            self.assert_code("RECURRENCE_UNSAFE", lambda: self.service.complete_task("synthetic-a", "execute"))
            self.assertIn("RECURRENCE_UNSAFE", self.service.complete_task("synthetic-a")["execution_blockers"])
        self.assertEqual(self.adapter.writes, [])

    def test_complete_verifies_status(self):
        self.assertEqual(self.service.complete_task("synthetic-a", "execute")["task"]["status"], "completed")
        self.assertEqual(self.adapter.tasks["synthetic-b"].status, "open")

    def test_permission_timeout_and_ambiguous_write_are_not_retried(self):
        for failure in [BridgeError("PERMISSION_DENIED", "Denied"),
                        BridgeError("TIMEOUT", "Timed out", outcome="unknown"), RuntimeError("private content")]:
            self.adapter.failure = failure
            self.adapter.writes.clear()
            with self.assertRaises(BridgeError) as caught:
                self.service.create_task({"title": "Synthetic"}, "execute")
            self.assertNotIn("private content", str(caught.exception))
            self.assertEqual(len(self.adapter.writes), 1)

    def test_unverified_success_and_failed_readback(self):
        self.adapter.ignore_fields = True
        error = self.assert_code("WRITE_UNVERIFIED", lambda: self.service.update_task("synthetic-a", {"notes": "New"}, "execute"))
        self.assertEqual(error.outcome, "accepted_unverified")
        self.assertEqual(len(self.adapter.writes), 1)
        self.adapter.after_write_read_error = True
        self.assert_code("WRITE_UNVERIFIED", lambda: self.service.create_task({"title": "T"}, "execute"))

    def test_unrequested_field_changes_fail_verification(self):
        original = self.adapter.update_task
        def unexpectedly_changes_deadline(id, fields, *, execution="preview"):
            result = original(id, fields, execution=execution)
            self.adapter.tasks[id] = replace(self.adapter.tasks[id], deadline=None)
            return result
        self.adapter.update_task = unexpectedly_changes_deadline
        self.assert_code("WRITE_UNVERIFIED", lambda: self.service.update_task("synthetic-a", {"notes": "New"}, "execute"))
        self.assertEqual(len(self.adapter.writes), 1)

    def test_missing_id_mutations_and_invalid_complete_readback(self):
        self.assert_code("NOT_FOUND", lambda: self.service.update_task("missing", {"notes": "New"}, "execute"))
        self.assert_code("NOT_FOUND", lambda: self.service.complete_task("missing", "execute"))
        self.assertEqual(self.adapter.writes, [])
        self.adapter.ignore_fields = True
        self.assert_code("WRITE_UNVERIFIED", lambda: self.service.complete_task("synthetic-a", "execute"))

    def test_adapter_rechecks_recurrence_after_service_read(self):
        original = self.adapter.get_task
        reads = 0
        def changes_between_calls(id):
            nonlocal reads
            reads += 1
            if reads == 2:
                self.adapter.tasks[id] = sample(recurrence="repeating")
            return original(id)
        self.adapter.get_task = changes_between_calls
        self.assert_code("RECURRENCE_UNSAFE", lambda: self.service.complete_task("synthetic-a", "execute"))
        self.assertEqual(self.adapter.writes, [])

    def test_invalid_receipt_is_not_success(self):
        self.adapter.bad_receipt = True
        self.assert_code("WRITE_UNVERIFIED", lambda: self.service.create_task({"title": "T"}, "execute"))

    def test_environment_opt_in_is_exact(self):
        for value in (None, "1", "yes", "TRUE", "true "):
            self.assertFalse(WritePolicy.from_env({"THINGS_ALLOW_WRITES": value}).enabled)
        self.assertTrue(WritePolicy.from_env({"THINGS_ALLOW_WRITES": "true"}).enabled)


if __name__ == "__main__":
    unittest.main()
