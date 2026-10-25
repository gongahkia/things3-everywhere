import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from things3_everywhere.adapter import ThingsAppleScriptAdapter, parse_task
from things3_everywhere.errors import BridgeError
from things3_everywhere.safety import WritePolicy
from things3_everywhere.transport import AppleScriptTransport, SCRIPT, dictionary_summary, find_app


def response(data, code=0, stderr=b""):
    return subprocess.CompletedProcess([], code, json.dumps(data).encode(), stderr)


ROW = ["synthetic-a", "Synthetic 雪", "Notes\n\\\"\x1e\x1f", "open", ["Example"], "2032-02-29"]


class AdapterTests(unittest.TestCase):
    def assert_code(self, code, fn):
        with self.assertRaises(BridgeError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_json_preserves_data_and_never_puts_content_in_arguments(self):
        content = '" \\ 雪\nend tell\ndo shell script "false"\x1e\x1f'
        run = Mock(return_value=response({"ok": True, "id": "synthetic-new"}))
        transport = AppleScriptTransport(WritePolicy(True), run=run, preflight=lambda: None)
        adapter = ThingsAppleScriptAdapter(WritePolicy(True), transport=transport)
        self.assertEqual(adapter.create_task({"title": "Synthetic", "notes": content}, execution="execute"), "synthetic-new")
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["/usr/bin/osascript", str(SCRIPT)])
        self.assertNotIn(content, str(args))
        self.assertEqual(json.loads(kwargs["input"])["fields"]["notes"], content)
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["timeout"], 20)

    def test_adapter_and_transport_each_enforce_gate(self):
        for enabled in (False, True):
            run = Mock()
            transport = AppleScriptTransport(WritePolicy(enabled), run=run, preflight=lambda: None)
            adapter = ThingsAppleScriptAdapter(WritePolicy(enabled), transport=transport)
            for choice in ("preview", "execute"):
                if enabled and choice == "execute":
                    continue
                expected = "EXECUTION_REQUIRED" if choice == "preview" else "READ_ONLY"
                for action in (
                    lambda: adapter.create_task({"title": "T"}, execution=choice),
                    lambda: adapter.update_task("synthetic-a", {"notes": "T"}, execution=choice),
                    lambda: adapter.complete_task("synthetic-a", execution=choice),
                    lambda: transport.call("create", {"fields": {"title": "T"}, "execution": choice}),
                ):
                    self.assert_code(expected, action)
            run.assert_not_called()

    def test_existing_mutations_are_unconditionally_blocked_for_live_adapter(self):
        transport = Mock()
        adapter = ThingsAppleScriptAdapter(WritePolicy(True), transport=transport)
        self.assert_code("RECURRENCE_UNSAFE", lambda: adapter.update_task("synthetic-a", {"notes": "x"}, execution="execute"))
        self.assert_code("RECURRENCE_UNSAFE", lambda: adapter.complete_task("synthetic-a", execution="execute"))
        transport.call.assert_not_called()

    def test_read_rows_and_actual_scope_are_explicit(self):
        transport = Mock()
        transport.call.return_value = {"rows": [ROW], "has_more": False}
        adapter = ThingsAppleScriptAdapter(transport=transport)
        page = adapter.list_tasks("Today", 5)
        transport.call.assert_called_once_with("today", {"limit": 5})
        self.assertEqual(page.tasks[0].notes, ROW[2])
        self.assertEqual(page.tasks[0].deadline, "2032-02-29")
        self.assertEqual(page.tasks[0].recurrence, "unknown")
        transport.call.return_value = {"row": ROW}
        self.assert_code("INVALID_RESPONSE", lambda: adapter.get_task("synthetic-other"))

    def test_malformed_rows_fail_without_partial_results(self):
        for row in (None, [], ROW[:-1], [*ROW[:3], "invalid", *ROW[4:]], [*ROW[:5], "not-a-date"]):
            self.assert_code("INVALID_RESPONSE", lambda: parse_task(row))

    def test_missing_app_stops_before_scripting(self):
        run = Mock()
        def missing():
            raise BridgeError("APP_NOT_FOUND", "Things 3 was not found.")
        transport = AppleScriptTransport(run=run, preflight=missing)
        self.assert_code("APP_NOT_FOUND", lambda: transport.call("today", {"limit": 1}))
        run.assert_not_called()
        with patch("things3_everywhere.transport.sys.platform", "linux"):
            self.assert_code("MACOS_REQUIRED", lambda: find_app())

    def test_permissions_timeout_and_errors_are_redacted(self):
        for number, code in ((-1743, "PERMISSION_DENIED"), (-1712, "TIMEOUT"), (-1728, "NOT_FOUND"), (7102, "UNKNOWN_TAG")):
            run = Mock(return_value=response({"ok": False, "error_number": number, "write_started": False}))
            transport = AppleScriptTransport(run=run, preflight=lambda: None)
            self.assert_code(code, lambda: transport.call("get", {"id": "synthetic-a"}))
        for result in (response({}, 1, b'private notes (-1743)'), response({"ok": False, "error_number": 123, "message": "private notes"})):
            transport = AppleScriptTransport(run=Mock(return_value=result), preflight=lambda: None)
            with self.assertRaises(BridgeError) as caught:
                transport.call("today", {"limit": 1})
            self.assertNotIn("private notes", str(caught.exception))
        run = Mock(side_effect=subprocess.TimeoutExpired(["private notes"], 20))
        transport = AppleScriptTransport(WritePolicy(True), run=run, preflight=lambda: None)
        error = self.assert_code("TIMEOUT", lambda: transport.call("create", {"execution": "execute", "fields": {"title": "T"}}))
        self.assertEqual(error.outcome, "unknown")
        run.assert_called_once()

    def test_ambiguous_and_partial_write_results(self):
        for data in ({"ok": False, "error_number": 5, "write_started": True},
                     {"ok": False, "error_number": -1712, "write_started": False}):
            transport = AppleScriptTransport(WritePolicy(True), run=Mock(return_value=response(data)), preflight=lambda: None)
            with self.assertRaises(BridgeError) as caught:
                transport.call("create", {"execution": "execute", "fields": {"title": "T"}})
            self.assertEqual(caught.exception.outcome, "unknown")
        run = Mock(return_value=subprocess.CompletedProcess([], 0, b'broken JSON', b''))
        transport = AppleScriptTransport(WritePolicy(True), run=run, preflight=lambda: None)
        error = self.assert_code("INVALID_RESPONSE", lambda: transport.call("create", {"execution": "execute", "fields": {"title": "T"}}))
        self.assertEqual(error.outcome, "unknown")

    def test_dictionary_probe_checks_terms_without_task_reads(self):
        xml = b'<dictionary><suite><class name="to do"/><class name="list"/><class name="tag"/>'
        xml += b''.join(b'<property name="' + p + b'"/>' for p in [b'id', b'name', b'notes', b'tag names', b'due date', b'status'])
        xml += b'</suite></dictionary>'
        run = Mock(return_value=subprocess.CompletedProcess([], 0, xml, b''))
        summary = dictionary_summary(Path('/synthetic/Things3.app'), run=run)
        self.assertTrue(summary["required_terms_present"])
        self.assertFalse(summary["recurrence_detection_supported"])
        self.assertEqual(run.call_args.args[0][0], "/usr/bin/sdef")

    @unittest.skipUnless(sys.platform == "darwin", "AppleScript helper test requires macOS")
    def test_pure_applescript_json_and_calendar_helpers(self):
        # Only the Foundation/date helpers are executed. No Things application
        # clause, task read, or mutation is included in this synthetic test.
        helpers = SCRIPT.read_text().split("on taskRow(t)")[0]
        script = helpers + '''
on run
    set raw to current application's NSFileHandle's fileHandleWithStandardInput()'s readDataToEndOfFile()
    set value to current application's NSJSONSerialization's JSONObjectWithData:raw options:0 |error|:(missing value)
    value's setObject:(my dateText(my calendarDate("2032-02-29"))) forKey:"date"
    return my jsonText(value)
end run
'''
        # MutableContainers option needed for this test's single dictionary edit.
        script = script.replace("JSONObjectWithData:raw options:0", "JSONObjectWithData:raw options:1")
        payload = {"content": ROW[2] + " 雪 🐢"}
        process = subprocess.run(["/usr/bin/osascript", "-e", script], input=json.dumps(payload).encode(),
                                 capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 0, "Synthetic AppleScript helpers failed")
        self.assertEqual(json.loads(process.stdout), {**payload, "date": "2032-02-29"})


if __name__ == "__main__":
    unittest.main()
