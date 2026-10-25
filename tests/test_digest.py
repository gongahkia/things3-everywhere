from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch

from things3_everywhere.briefing import briefing, read_only_service
from things3_everywhere.digest import format_digest, local_day, split_message
from things3_everywhere.errors import BridgeError
from things3_everywhere.service import ThingsService
from test_service import FakeAdapter, sample


class DigestTests(unittest.TestCase):
    now = datetime(2026, 10, 24, 16, 30, tzinfo=timezone.utc)

    def test_empty_populated_and_notes_excluded(self):
        self.assertIn("No tasks", format_digest({"tasks": []}, now=self.now))
        page = {"tasks": [sample().public()]}
        text = format_digest(page, now=self.now)
        self.assertIn("2026-10-25 (Asia/Singapore)", text)
        self.assertIn("deadline 2030-04-05", text)
        self.assertNotIn("Original notes", text)
        self.assertNotIn("start date", text)

    def test_boundaries_timezone_and_invalid_dates(self):
        for instant, zone, day in [
            ("2026-10-24T15:59:59+00:00", "Asia/Singapore", "2026-10-24"),
            ("2026-10-24T16:00:00+00:00", "Asia/Singapore", "2026-10-25"),
            ("2026-10-24T16:00:00+00:00", "UTC", "2026-10-24"),
            ("2026-03-08T07:00:00+00:00", "America/New_York", "2026-03-08"),
        ]:
            self.assertEqual(local_day(datetime.fromisoformat(instant), zone), day)
        with self.assertRaises(BridgeError):
            local_day(self.now, "Invalid/Zone")
        with self.assertRaises(BridgeError):
            local_day(datetime(2026, 1, 1))

    def test_order_duplicates_and_partial_page_notice(self):
        a = sample("a").public()
        b = sample("b", title="First").public()
        c = sample("c").public()
        text = format_digest({"tasks": [b, a, a, c], "has_more": True}, now=self.now)
        self.assertLess(text.index("First"), text.index("Duplicate title"))
        self.assertEqual(text.count("• Duplicate title"), 2)
        self.assertIn("PARTIAL LIST", text)

    def test_missing_unreliable_and_repeating_deadlines_are_omitted(self):
        for patch in ({"deadline": None}, {"deadline": "2026-02-30"}, {"recurrence": "unknown"},
                      {"recurrence": "repeating"}, {"deadline": "20260220"}):
            row = sample().public() | patch
            self.assertNotIn(" — deadline ", format_digest({"tasks": [row]}, now=self.now))
        row = sample().public()
        del row["deadline"]
        self.assertNotIn(" — deadline ", format_digest({"tasks": [row]}, now=self.now))

    def test_unicode_long_messages_preserve_every_code_point(self):
        text = ('"quoted" \\ 中文 👨‍👩‍👧‍👦 e\u0301\n' * 600)
        chunks = split_message(text)
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c.encode("utf-16-le")) // 2 <= 4096 for c in chunks))
        self.assertEqual(len(split_message("🧪" * 2048)), 1)
        for invalid in ("", "\ud800"):
            with self.assertRaises(BridgeError):
                split_message(invalid)

    def test_multiline_controls_do_not_disappear(self):
        text = format_digest({"tasks": [sample(title="line\nnext\x1b").public()]}, now=self.now)
        self.assertIn("line\n  next\\u001b", text)

    def test_fake_preview_never_reads_things_or_calls_sender(self):
        def forbidden(*args, **kwargs):
            self.fail("unexpected external boundary")
        result = briefing(fake=True, service_factory=forbidden, sender=forbidden, now=self.now)
        self.assertEqual(result["source"], "synthetic")
        self.assertEqual(result["requests"], 0)

    def test_live_preview_uses_existing_adapter_and_never_writes(self):
        adapter = FakeAdapter([sample()])
        result = briefing(service_factory=lambda: ThingsService(adapter), now=self.now,
                          sender=lambda *a, **k: self.fail("Telegram called"))
        self.assertEqual(result["source"], "live_things")
        self.assertEqual(adapter.reads, ["Today"])
        self.assertEqual(adapter.writes, [])

    def test_live_digest_forces_read_only_even_if_shell_opted_into_writes(self):
        with patch.dict(os.environ, {"THINGS_ALLOW_WRITES": "true"}):
            service = read_only_service()
        self.assertFalse(service.policy.enabled)
        self.assertFalse(service.adapter.policy.enabled)

    def test_send_choice_is_explicit_and_timezone_configurable(self):
        calls = []
        def sender(text, **kwargs):
            calls.append(kwargs["execute"])
            return {"outcome": "mock"}
        for execute in (False, True):
            briefing(action="send-once", fake=True, execute=execute, env={}, sender=sender, now=self.now)
        self.assertEqual(calls, [False, True])
        with self.assertRaises(BridgeError):
            briefing(execute=True)
        result = briefing(fake=True, env={"BRIEFING_TIMEZONE": "UTC"}, now=self.now)
        self.assertIn("2026-10-24 (UTC)", result["text"])


if __name__ == "__main__":
    unittest.main()
