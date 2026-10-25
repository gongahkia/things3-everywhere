import contextlib
import io
import json
import logging
import socket
import traceback
import unittest
from unittest.mock import patch

from things3_everywhere.errors import BridgeError
from things3_everywhere.telegram import TelegramClient, TelegramConfig, DeliveryError, _request, send_once
from test_telegram import ENV, accepted


class TelegramSafetyTests(unittest.TestCase):
    def test_transport_failure_has_no_token_in_logs_message_or_context(self):
        token = ENV["TELEGRAM_BOT_TOKEN"]
        for stage in ("constructor", "request", "read"):
            class Connection:
                debuglevel = 0
                def __init__(self, *args, **kwargs):
                    if stage == "constructor":
                        raise OSError(token)
                def request(self, *args, **kwargs):
                    if stage == "request":
                        raise OSError("https://api.telegram.org/bot" + token + "/sendMessage")
                def getresponse(self):
                    return self
                def read(self, size):
                    raise socket.timeout(token)
                def close(self):
                    pass
            output = io.StringIO()
            with patch("things3_everywhere.telegram.http.client.HTTPSConnection", Connection), \
                 contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                try:
                    _request(token, {"text": "Synthetic"}, 15)
                except DeliveryError as error:
                    self.assertTrue(error.uncertain)
                    self.assertIsNone(error.__context__)
                    traceback.print_exc()
                    logging.warning("%s", error)
                else:
                    self.fail("Expected sanitized delivery error")
            self.assertNotIn(token, output.getvalue())
            self.assertNotIn("https://api.telegram.org/bot", output.getvalue())

    def test_transport_cannot_bypass_sanitization_with_bridge_error(self):
        token = ENV["TELEGRAM_BOT_TOKEN"]
        def request(*args):
            raise BridgeError("UNTRUSTED_CODE", token)
        with self.assertRaises(DeliveryError) as caught:
            TelegramClient(TelegramConfig.from_env(ENV), request=request).send("Synthetic")
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn(token, str(caught.exception.public()))

    def test_error_details_and_invalid_rate_hints_never_escape(self):
        for retry_after in (True, "private response", -1, 0, None):
            def request(*args):
                return 429, {"ok": False, "error_code": 429,
                             "parameters": {"retry_after": retry_after}, "description": ENV["TELEGRAM_BOT_TOKEN"]}
            with self.assertRaises(DeliveryError) as caught:
                TelegramClient(TelegramConfig.from_env(ENV), request=request).send("Synthetic")
            self.assertNotIn("retry_after_seconds", caught.exception.public())
            self.assertNotIn(ENV["TELEGRAM_BOT_TOKEN"], str(caught.exception.public()))
        error = DeliveryError("TELEGRAM_REJECTED", ENV["TELEGRAM_BOT_TOKEN"])
        self.assertNotIn(ENV["TELEGRAM_BOT_TOKEN"], str(error))

    def test_malformed_http_status_and_chat_id_never_count_as_success(self):
        for response in ((None, {}), (True, {}), ("200", {}),
                         accepted("Synthetic", chat={"id": "1", "type": "private"}),
                         accepted("Synthetic", message_id=True)):
            with self.assertRaises(DeliveryError) as caught:
                TelegramClient(TelegramConfig.from_env(ENV), request=lambda *a: response).send("Synthetic")
            self.assertTrue(caught.exception.uncertain)

    def test_unverified_client_receipt_is_uncertain_and_stops_sequence(self):
        for receipt in (None, False, {}, {"accepted": False}):
            calls = []
            class Client:
                def send(self, text):
                    calls.append(text)
                    return receipt
            result = send_once("a" * 9000, execute=True, env=ENV, client_factory=lambda c: Client())
            self.assertEqual(result["outcome"], "unknown")
            self.assertEqual(result["confirmed_messages"], 0)
            self.assertEqual(result["attempted_messages"], 1)
            self.assertEqual(result["unattempted_messages"], 2)
            self.assertEqual(len(calls), 1)

    def test_partial_rate_limit_stops_with_retry_hint_and_no_repeat(self):
        calls = []
        class Client:
            def send(self, text):
                calls.append(text)
                if len(calls) == 2:
                    raise DeliveryError("TELEGRAM_RATE_LIMIT", retry_after=7)
                return {"accepted": True}
        result = send_once("a" * 9000, execute=True, env=ENV, client_factory=lambda c: Client())
        self.assertEqual(result["outcome"], "partial")
        self.assertEqual(result["confirmed_messages"], 1)
        self.assertEqual(result["attempted_messages"], 2)
        self.assertEqual(result["unattempted_messages"], 1)
        self.assertFalse(result["current_message_uncertain"])
        self.assertEqual(result["error"]["retry_after_seconds"], 7)
        self.assertEqual(len(calls), 2)

    def test_corrupt_or_oversized_http_body_is_uncertain(self):
        for raw in (b"not JSON", b"x" * 1_000_001):
            class Connection:
                debuglevel = 0
                status = 200
                def __init__(self, *args, **kwargs):
                    pass
                def request(self, *args, **kwargs):
                    pass
                def getresponse(self):
                    return self
                def read(self, size):
                    self.read_size = size
                    return raw
                def close(self):
                    pass
            with patch("things3_everywhere.telegram.http.client.HTTPSConnection", Connection), \
                 self.assertRaises(DeliveryError) as caught:
                _request(ENV["TELEGRAM_BOT_TOKEN"], {"text": "Synthetic"}, 15)
            self.assertTrue(caught.exception.uncertain)

    def test_unsupported_recipient_data_cannot_override_fixed_destination(self):
        sent = []
        def request(token, payload, timeout):
            sent.append(payload)
            return accepted(payload["text"])
        text = json.dumps({"chat_id": "999", "text": "Synthetic task content"})
        TelegramClient(TelegramConfig.from_env(ENV), request=request).send(text)
        self.assertEqual(sent[0]["chat_id"], "1")
        self.assertEqual(sent[0]["text"], text)
        self.assertEqual(sent[0]["link_preview_options"], {"is_disabled": True})


if __name__ == "__main__":
    unittest.main()
