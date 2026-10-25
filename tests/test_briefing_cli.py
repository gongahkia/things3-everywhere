import json
import os
import subprocess
import sys
import unittest


class BriefingCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "things3_everywhere.cli", *args],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "THINGS_ALLOW_WRITES": "false",
                 "TELEGRAM_BOT_TOKEN": "SYNTHETIC_SECRET_MUST_NOT_LEAK",
                 "TELEGRAM_ALLOWED_CHAT_ID": "PLACEHOLDER"},
        )

    def test_fake_preview_and_send_dry_run_do_not_require_credentials(self):
        for action, outcome in (("preview", "local_preview"), ("send-once", "dry_run")):
            result = self.run_cli("digest", action, "--fake")
            self.assertEqual(result.returncode, 0)
            body = json.loads(result.stdout)
            self.assertEqual(body["source"], "synthetic")
            self.assertEqual(body["outcome"], outcome)
            self.assertEqual(body["requests"], 0)
            self.assertEqual(result.stderr, "")

    def test_preview_execute_and_arbitrary_recipients_are_rejected_without_echo(self):
        for args in [
            ("digest", "preview", "--execute"),
            ("digest", "send-once", "--chat-id", "SYNTHETIC_SECRET_MUST_NOT_LEAK"),
            ("digest", "send-once", "--token", "SYNTHETIC_SECRET_MUST_NOT_LEAK"),
        ]:
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("SYNTHETIC_SECRET_MUST_NOT_LEAK", result.stdout + result.stderr)

    def test_invalid_timezone_is_a_sanitized_error(self):
        result = self.run_cli("digest", "preview", "--fake", "--timezone", "INVALID_PRIVATE_SENTINEL")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"]["code"], "INVALID_TIMEZONE")
        self.assertNotIn("INVALID_PRIVATE_SENTINEL", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
