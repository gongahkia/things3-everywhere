from datetime import datetime, timezone, tzinfo
import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

from things3_everywhere.briefing import briefing, read_only_service
from things3_everywhere.cli import main
from things3_everywhere.digest import format_digest, local_day, split_message
from things3_everywhere.errors import BridgeError


class DigestSafetyTests(unittest.TestCase):
    now = datetime(2030, 4, 4, 16, tzinfo=timezone.utc)

    def test_read_only_composition_ignores_global_write_opt_in(self):
        with patch.dict(os.environ, {"THINGS_ALLOW_WRITES": "true"}):
            service = read_only_service()
        self.assertFalse(service.policy.enabled)
        self.assertFalse(service.adapter.policy.enabled)
        self.assertFalse(service.adapter.transport.policy.enabled)

    def test_bad_options_fail_before_live_reads(self):
        for options in ({"zone": ""}, {"zone": "Invalid/PrivateZone"}, {"now": "invalid"},
                        {"execute": "true"}, {"fake": 1}, {"action": "poll"}):
            with self.subTest(options=options), self.assertRaises(BridgeError):
                briefing(service_factory=lambda: self.fail("Unexpected live read"), **options)

    def test_malformed_structured_data_is_explicit(self):
        for page in ({"tasks": None}, {"tasks": [None]}, {"tasks": [{"id": "a"}]},
                     {"tasks": [], "has_more": "true"},
                     {"tasks": [{"id": "a", "title": "\ud800"}]}):
            with self.subTest(page=page), self.assertRaises(BridgeError) as caught:
                format_digest(page, now=self.now)
            self.assertEqual(caught.exception.code, "INVALID_INPUT")

    def test_determinism_and_no_dependency_on_host_timezone(self):
        page = {"tasks": [{"id": "synthetic-a", "title": "Read 雪", "notes": "PRIVATE_NOTES",
                           "tags": ["PRIVATE_TAG"], "deadline": None}], "has_more": False}
        with patch.dict(os.environ, {"TZ": "America/Los_Angeles"}):
            first = format_digest(page, now=self.now)
        with patch.dict(os.environ, {"TZ": "UTC"}):
            second = format_digest(page, now=self.now)
        self.assertEqual(first, second)
        self.assertIn("2030-04-05", first)
        self.assertNotIn("PRIVATE_", first)
        self.assertNotIn("synthetic-a", first)

    def test_timezone_with_no_offset_is_not_assumed_to_be_local(self):
        class NoOffset(tzinfo):
            def utcoffset(self, dt):
                return None
        with self.assertRaises(BridgeError):
            local_day(self.now.replace(tzinfo=NoOffset()))

    def test_long_title_is_preserved_across_chunks(self):
        title = "Synthetic 🐢 e\u0301 雪 " * 1000
        digest = format_digest({"tasks": [{"id": "a", "title": title}]}, now=self.now)
        chunks = split_message(digest)
        self.assertIn(title, digest)
        self.assertEqual("".join(chunks), digest)
        self.assertTrue(all(len(c.encode("utf-16-le")) // 2 <= 4096 for c in chunks))

    def test_credentials_never_enable_preview_or_dry_run(self):
        env = {"TELEGRAM_BOT_TOKEN": "12345:" + "SYNTHETIC_" * 4, "TELEGRAM_ALLOWED_CHAT_ID": "1"}
        with patch("http.client.HTTPSConnection", side_effect=AssertionError("Network forbidden")):
            for action in ("preview", "send-once"):
                result = briefing(action=action, fake=True, env=env, now=self.now)
                self.assertEqual(result["requests"], 0)

    def test_cli_exit_codes_reflect_delivery_outcome(self):
        for outcome, expected in (("accepted", 0), ("dry_run", 0), ("partial", 1), ("unknown", 1), ("rejected", 1)):
            output = io.StringIO()
            with patch("sys.argv", ["things3-everywhere", "digest", "send-once", "--fake", "--execute"]), \
                 patch("things3_everywhere.cli.briefing", return_value={"outcome": outcome}) as mock, \
                 contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as caught:
                main()
            self.assertEqual(caught.exception.code, expected)
            self.assertTrue(mock.call_args.kwargs["execute"])
            self.assertEqual(json.loads(output.getvalue())["outcome"], outcome)


if __name__ == "__main__":
    unittest.main()
