import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import unittest

from things3_everywhere.cli import summarize
from things3_everywhere.errors import BridgeError
from things3_everywhere.safety import WritePolicy
from things3_everywhere.service import ThingsService
from things3_everywhere.tools import TOOL_DEFINITIONS, dispatch
from test_service import FakeAdapter, sample


class ProtocolTests(unittest.TestCase):
    def start(self, enabled=False):
        env = {**os.environ, "TEST_ENABLE_FAKE_WRITES": "true" if enabled else "false"}
        self.process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("fake_server.py"))],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, env=env)
        self.sequence = 0
        self.addCleanup(self.stop)
        result = self.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                            "clientInfo": {"name": "synthetic-test", "version": "1"}})
        self.assertIn("serverInfo", result["result"])
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def stop(self):
        process = getattr(self, "process", None)
        if process is None:
            return
        if process.poll() is None:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                self.fail("Fake MCP server failed to stop on stdin EOF")
        stderr = process.stderr.read()
        stdout = process.stdout.read()
        process.stdout.close()
        process.stderr.close()
        self.process = None
        self.assertEqual(process.returncode, 0)
        self.assertEqual(stdout, "", "Unexpected stdout outside requested protocol replies")
        self.assertIn("details suppressed", stderr)
        self.assertNotIn("PRIVATE_LOG_SENTINEL", stderr)
        self.assertNotIn("secret synthetic notes", stderr)

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.sequence += 1
        self.send({"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params})
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=15), "MCP response timed out")
            line = self.process.stdout.readline()
        result = json.loads(line)
        self.assertEqual(result["jsonrpc"], "2.0")
        self.assertEqual(result["id"], self.sequence)
        return result

    def call(self, name, arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})["result"]
        self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])
        return result

    def test_stdio_handshake_reads_defaults_and_all_mutation_gates(self):
        self.start()
        tools = self.request("tools/list", {})["result"]["tools"]
        self.assertEqual(len(tools), 7)
        self.assertEqual({t["name"] for t in tools}, {t["name"] for t in TOOL_DEFINITIONS})
        for name in ("things_today", "things_inbox"):
            self.assertFalse(self.call(name, {})["isError"])
        self.assertEqual(self.call("things_search", {"query": "not present"})["structuredContent"]["count"], 0)
        self.assertEqual(self.call("things_get_task", {"id": "missing"})["structuredContent"]["error"]["code"], "NOT_FOUND")
        self.assertEqual(self.call("things_get_task", {"id": "synthetic-a"})["structuredContent"]["task"]["id"], "synthetic-a")
        for name, arguments in [("things_create_task", {"fields": {"title": "T"}}),
                                ("things_update_task", {"id": "synthetic-a", "fields": {"notes": "New"}}),
                                ("things_complete_task", {"id": "synthetic-a"})]:
            preview = self.call(name, arguments)
            self.assertEqual(preview["structuredContent"]["outcome"], "preview")
            denied = self.call(name, {**arguments, "execution": "execute"})
            self.assertTrue(denied["isError"])
            self.assertEqual(denied["structuredContent"]["error"]["code"], "READ_ONLY")
        unknown = self.call("things_delete_task", {"id": "synthetic-a"})
        self.assertEqual(unknown["structuredContent"]["error"]["code"], "UNKNOWN_TOOL")
        invalid = self.call("things_get_task", {"id": "PRIVATE_INPUT_SENTINEL ", "extra": "private notes"})
        self.assertNotIn("PRIVATE_INPUT_SENTINEL", json.dumps(invalid))
        self.assertNotIn("private notes", json.dumps(invalid))

    def test_fake_execution_and_preview_even_with_opt_in(self):
        self.start(enabled=True)
        preview = self.call("things_update_task", {"id": "synthetic-a", "fields": {"notes": "Changed"}})
        self.assertEqual(preview["structuredContent"]["outcome"], "preview")
        before = self.call("things_get_task", {"id": "synthetic-a"})["structuredContent"]["task"]
        self.assertEqual(before["notes"], "Original notes")
        changed = self.call("things_update_task", {"id": "synthetic-a", "fields": {"notes": ""}, "execution": "execute"})
        self.assertEqual(changed["structuredContent"]["outcome"], "verified")
        self.assertEqual(changed["structuredContent"]["task"]["notes"], "")
        self.assertEqual(changed["structuredContent"]["task"]["deadline"], "2030-04-05")
        completed = self.call("things_complete_task", {"id": "synthetic-a", "execution": "execute"})
        self.assertEqual(completed["structuredContent"]["task"]["status"], "completed")
        created = self.call("things_create_task", {"fields": {"title": "Synthetic 雪", "notes": '"\\\nUnicode 🐢'}, "execution": "execute"})
        self.assertEqual(created["structuredContent"]["outcome"], "verified")

    def test_dispatch_sanitizes_failures_and_rejects_unknown_fields(self):
        adapter = FakeAdapter([sample()])
        service = ThingsService(adapter, WritePolicy(True))
        for code in ("PERMISSION_DENIED", "TIMEOUT"):
            def fail(*args):
                raise BridgeError(code, "Synthetic failure.")
            adapter.get_task = fail
            result, is_error = dispatch(service, "things_get_task", {"id": "synthetic-a"})
            self.assertTrue(is_error)
            self.assertEqual(result["error"]["code"], code)
        def unexpected(*args):
            raise RuntimeError("PRIVATE_SENTINEL")
        adapter.get_task = unexpected
        result, is_error = dispatch(service, "things_get_task", {"id": "synthetic-a"})
        self.assertTrue(is_error)
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))
        result, _ = dispatch(service, "things_create_task", {"fields": {"title": "T", "start_date": "2030-01-01"}})
        self.assertEqual(result["error"]["code"], "UNSUPPORTED_FIELD")

    def test_cli_summary_omits_personal_content(self):
        task = sample().public()
        result = summarize({"tasks": [task], "count": 1, "limit": 5, "has_more": False})
        self.assertEqual(result, {"count": 1, "limit": 5, "has_more": False})
        self.assertEqual(summarize({"task": task}), {"count": 1, "outcome": "read"})


if __name__ == "__main__":
    unittest.main()
