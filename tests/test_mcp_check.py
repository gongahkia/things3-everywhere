"""Diagnostic tests: synthetic transport or deliberately absent app fixture only."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from scripts.check_mcp import CheckFailed, LIMIT, call, check_session
from things3_everywhere.tools import TOOL_DEFINITIONS


ROOT = Path(__file__).resolve().parents[1]


class SyntheticSession:
    def __init__(self, page=None):
        self.page = page or {"tasks": [], "count": 0, "limit": LIMIT, "has_more": False}
        self.calls = []

    async def initialize(self):
        return SimpleNamespace(serverInfo=SimpleNamespace(name="things3-everywhere"))

    async def list_tools(self):
        return SimpleNamespace(tools=[SimpleNamespace(name=t["name"]) for t in TOOL_DEFINITIONS])

    async def call_tool(self, name, arguments):
        if name not in {"things_today", "things_inbox", "things_search", "things_get_task"}:
            raise AssertionError("Diagnostic attempted mutation")
        self.calls.append((name, arguments))
        body = deepcopy(self.page)
        return SimpleNamespace(structuredContent=body, isError=False,
                               content=[SimpleNamespace(type="text", text=json.dumps(body))])


class McpCheckUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_results_skip_lookup_and_format_digest_without_mutation(self):
        session, checks = SyntheticSession(), {}
        await check_session(session, checks)
        self.assertEqual(checks["things_get_task"]["status"], "SKIPPED")
        self.assertEqual(checks["digest"]["status"], "PASS")
        self.assertEqual([name for name, _ in session.calls],
                         ["things_today", "things_inbox", "things_search"])
        for _, arguments in session.calls:
            self.assertEqual(arguments["limit"], 3)
            self.assertFalse(arguments["include_notes"])

    async def test_malformed_success_is_rejected(self):
        cases = [
            {"tasks": [], "count": 1, "limit": LIMIT, "has_more": False},
            {"tasks": [], "count": 0, "limit": True, "has_more": False},
            {"tasks": [{"title": "PRIVATE_SYNTHETIC_CONTENT"}], "count": 1,
             "limit": LIMIT, "has_more": False},
        ]
        for page in cases:
            with self.subTest(page_shape=list(page)):
                with self.assertRaises(CheckFailed) as caught:
                    await check_session(SyntheticSession(page), {})
                self.assertEqual(caught.exception.code, "INVALID_RESPONSE")
                self.assertNotIn("PRIVATE_SYNTHETIC_CONTENT", str(caught.exception))

    async def test_unknown_error_detail_cannot_enter_public_diagnostic(self):
        class ErrorSession:
            async def call_tool(self, name, arguments):
                body = {"error": {"code": "PRIVATE_SYNTHETIC_CODE", "message": "PRIVATE_NOTES"}}
                return SimpleNamespace(structuredContent=body, isError=True,
                                       content=[SimpleNamespace(type="text", text=json.dumps(body))])
        with self.assertRaises(CheckFailed) as caught:
            await call(ErrorSession(), "things_today", {"limit": 3})
        self.assertEqual(caught.exception.code, "TOOL_ERROR")
        self.assertNotIn("PRIVATE", str(caught.exception))


class McpCheckCliTests(unittest.TestCase):
    def run_check(self, *args, app_path=None):
        env = {**os.environ, "THINGS_ALLOW_WRITES": "false", "TEST_ENABLE_FAKE_WRITES": "false"}
        if app_path:
            env["THINGS_APP_PATH"] = str(app_path)
        return subprocess.run([sys.executable, str(ROOT / "scripts/check_mcp.py"), *args],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)

    def test_fake_counts_only_through_production_main(self):
        result = self.run_check("--fake")
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["source"], "synthetic")
        self.assertEqual(body["status"], "PASS")
        self.assertEqual(body["checks"]["things_today"]["count"], 2)
        self.assertEqual(body["checks"]["things_get_task"]["status"], "PASS")
        self.assertEqual(body["telegram_requests"], 0)
        self.assertFalse(body["writes_enabled"])
        for private in ("synthetic-a", "Duplicate title", "Original notes", "PRIVATE_LOG_SENTINEL"):
            self.assertNotIn(private, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")

    @unittest.skipUnless(sys.platform == "darwin", "Missing-app preflight requires macOS")
    def test_live_backend_absent_fixture_is_blocked_without_fake_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_check("--live", app_path=Path(directory) / "AbsentFixture.app")
        self.assertEqual(result.returncode, 1)
        body = json.loads(result.stdout)
        self.assertEqual(body["source"], "live_read_only")
        self.assertEqual(body["status"], "BLOCKED")
        self.assertEqual(body["error_code"], "APP_NOT_FOUND")
        self.assertEqual(set(body["checks"]), {"transport"})
        self.assertNotIn("AbsentFixture", result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")

    def test_mode_must_be_explicit(self):
        for args in ((), ("--fake", "--live")):
            result = self.run_check(*args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
