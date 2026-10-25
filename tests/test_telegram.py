import contextlib
import http.client
import io
import socket
import traceback
import unittest
from unittest.mock import patch

from things3_everywhere.errors import BridgeError
from things3_everywhere.telegram import TelegramClient, TelegramConfig, DeliveryError, send_once

# Deliberately synthetic. Never transmitted, even if the developer has real credentials.
ENV = {"TELEGRAM_BOT_TOKEN": "12345:" + "SYNTHETIC_" * 4, "TELEGRAM_ALLOWED_CHAT_ID": "1"}


def accepted(text, **changes):
    return 200, {"ok": True, "result": {"message_id": 1, "chat": {"id": 1, "type": "private"},
                                      "text": text, **changes}}


class TelegramTests(unittest.TestCase):
    def test_dry_run_no_credentials_or_client(self):
        result = send_once("Synthetic", client_factory=lambda c: self.fail("client constructed"))
        self.assertEqual(result["outcome"], "dry_run")
        self.assertEqual(result["requests"], 0)

    def test_missing_invalid_and_private_destination_config(self):
        for env in ({}, ENV | {"TELEGRAM_BOT_TOKEN": "placeholder"},
                    ENV | {"TELEGRAM_ALLOWED_CHAT_ID": "@someone"},
                    ENV | {"TELEGRAM_ALLOWED_CHAT_ID": "-1"},
                    ENV | {"TELEGRAM_ALLOWED_CHAT_ID": "9007199254740993"}):
            with self.assertRaises(BridgeError):
                TelegramConfig.from_env(env)
        self.assertNotIn(ENV["TELEGRAM_BOT_TOKEN"], repr(TelegramConfig.from_env(ENV)))

    def test_plain_text_allowlist_and_timeout(self):
        calls = []
        def request(token, payload, timeout):
            calls.append(payload)
            self.assertEqual(timeout, 15)
            self.assertEqual(payload["chat_id"], "1")
            self.assertNotIn("parse_mode", payload)
            return accepted(payload["text"])
        client = TelegramClient(TelegramConfig.from_env(ENV), request=request)
        self.assertEqual(client.send("chat_id=999 is only task text"), {"accepted": True})
        self.assertEqual(len(calls), 1)

    def test_actual_http_transport_is_mocked_and_does_not_follow_redirects(self):
        from things3_everywhere.telegram import _request
        class Response:
            status = 302
            def read(self, limit):
                return b'{"ok":false,"error_code":302}'
        class Connection:
            debuglevel = 0
            def __init__(self, host, timeout):
                self.host, self.timeout = host, timeout
                self.calls = 0
            def request(self, method, path, **kwargs):
                self.calls += 1
                assert method == "POST" and path.endswith("/sendMessage")
            def getresponse(self):
                return Response()
            def close(self):
                pass
        with patch("things3_everywhere.telegram.http.client.HTTPSConnection", Connection):
            status, body = _request(ENV["TELEGRAM_BOT_TOKEN"], {"text": "Synthetic"}, 15)
        self.assertEqual(status, 302)

    def test_debug_logging_blocks_before_request(self):
        with patch.object(http.client.HTTPConnection, "debuglevel", 1):
            with self.assertRaises(BridgeError):
                send_once("Synthetic", execute=True, env=ENV,
                          client_factory=lambda c: self.fail("must fail before client"))

    def test_success_requires_matching_chat_text_and_valid_receipt(self):
        for response in ((200, None), (200, {"ok": True}), (500, {"ok": True}),
                         accepted("different"), accepted("Synthetic", message_id="x"),
                         accepted("Synthetic", chat={"id": 2, "type": "private"})):
            client = TelegramClient(TelegramConfig.from_env(ENV), request=lambda *a: response)
            with self.assertRaises(DeliveryError) as caught:
                client.send("Synthetic")
            self.assertTrue(caught.exception.uncertain)

    def test_explicit_errors_rate_limit_and_no_retry(self):
        for status, code in ((401, "TELEGRAM_AUTH"), (403, "TELEGRAM_AUTH"), (400, "TELEGRAM_CHAT"),
                             (404, "TELEGRAM_CHAT"), (500, "TELEGRAM_REJECTED"), (429, "TELEGRAM_RATE_LIMIT")):
            calls = []
            def request(*args):
                calls.append(1)
                return status, {"ok": False, "error_code": status, "description": ENV["TELEGRAM_BOT_TOKEN"],
                                "parameters": {"retry_after": 12}}
            client = TelegramClient(TelegramConfig.from_env(ENV), request=request)
            with self.assertRaises(DeliveryError) as caught:
                client.send("Synthetic")
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn(ENV["TELEGRAM_BOT_TOKEN"], str(caught.exception.public()))
            if status == 429:
                self.assertEqual(caught.exception.retry_after, 12)
            self.assertEqual(len(calls), 1)

    def test_ambiguous_timeout_suppresses_token_in_logs_and_traceback(self):
        token = ENV["TELEGRAM_BOT_TOKEN"]
        def request(*args):
            raise socket.timeout("https://api.telegram.org/bot" + token + "/sendMessage")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                TelegramClient(TelegramConfig.from_env(ENV), request=request).send("Synthetic")
            except DeliveryError as error:
                self.assertTrue(error.uncertain)
                traceback.print_exc()
        self.assertNotIn(token, output.getvalue())
        self.assertNotIn("https://api.telegram.org/bot", output.getvalue())

    def test_partial_delivery_and_unattempted_count(self):
        calls = []
        class Client:
            def send(self, text):
                calls.append(text)
                if len(calls) == 2:
                    raise DeliveryError("DELIVERY_UNCERTAIN", "Synthetic timeout", uncertain=True)
                return {"accepted": True}
        result = send_once("a" * 9000, execute=True, env=ENV, client_factory=lambda c: Client())
        self.assertEqual(result["outcome"], "partial")
        self.assertEqual(result["confirmed_messages"], 1)
        self.assertEqual(result["unattempted_messages"], 1)
        self.assertTrue(result["current_message_uncertain"])
        self.assertEqual(result["failed_message"], 2)
        self.assertEqual(len(calls), 2)

    def test_all_accepted_and_first_message_rejection(self):
        class Client:
            def send(self, text):
                return {"accepted": True}
        self.assertEqual(send_once("Synthetic", execute=True, env=ENV,
                                  client_factory=lambda c: Client())["outcome"], "accepted")
        class Reject:
            def send(self, text):
                raise DeliveryError("TELEGRAM_RATE_LIMIT", "Synthetic limit")
        self.assertEqual(send_once("Synthetic", execute=True, env=ENV,
                                  client_factory=lambda c: Reject())["outcome"], "rejected")


if __name__ == "__main__":
    unittest.main()
