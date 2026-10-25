"""Explicit outbound Telegram delivery. No logging, listener, persistence or retry."""

from dataclasses import dataclass, field
import http.client
import json
import os
import re

from .digest import split_message
from .errors import BridgeError


@dataclass(frozen=True)
class TelegramConfig:
    token: str = field(repr=False)
    chat_id: str = field(repr=False)

    def __post_init__(self):
        if (not isinstance(self.token, str) or
                not re.fullmatch(r"[1-9][0-9]{4,15}:[A-Za-z0-9_-]{30,100}", self.token) or
                not isinstance(self.chat_id, str) or
                not re.fullmatch(r"[1-9][0-9]{0,15}", self.chat_id) or int(self.chat_id) >= 2**52):
            raise BridgeError("TELEGRAM_CONFIG", "Configure a bot token and one positive numeric private chat ID.")

    @classmethod
    def from_env(cls, env):
        return cls(env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_ALLOWED_CHAT_ID"))


ERROR_MESSAGES = {
    "DELIVERY_UNCERTAIN": "Delivery could not be verified. Check Telegram before any manual retry.",
    "TELEGRAM_RATE_LIMIT": "Telegram rate-limited this message; no retry was made.",
    "TELEGRAM_AUTH": "Telegram rejected credentials or bot access; check the token and whether the bot is blocked.",
    "TELEGRAM_CHAT": "Telegram rejected the destination or request; check bot setup and the configured private chat.",
    "TELEGRAM_REJECTED": "Telegram explicitly rejected the request; no retry was made.",
}


class DeliveryError(BridgeError):
    def __init__(self, code, message=None, *, uncertain=False, retry_after=None):
        # Caller/server text is never used as an error message, even at this seam.
        code = code if code in ERROR_MESSAGES else "DELIVERY_UNCERTAIN"
        self.uncertain = code == "DELIVERY_UNCERTAIN" or uncertain is True
        super().__init__(code, ERROR_MESSAGES[code], outcome="unknown" if self.uncertain else "rejected")
        self.retry_after = (retry_after if code == "TELEGRAM_RATE_LIMIT"
                            and type(retry_after) is int and retry_after > 0 else None)

    def public(self):
        result = super().public()
        if self.retry_after is not None:
            result["retry_after_seconds"] = self.retry_after
        return result


def uncertain():
    return DeliveryError("DELIVERY_UNCERTAIN", "Delivery could not be verified. Check Telegram before any manual retry.",
                         uncertain=True)


def _require_quiet_http():
    # http.client is quiet by default, but global debug mode exposes request paths.
    if http.client.HTTPConnection.debuglevel or http.client.HTTPSConnection.debuglevel:
        raise BridgeError("TELEGRAM_CONFIG", "Disable HTTP debugging before sending.")


def _request(token, payload, timeout):
    _require_quiet_http()
    connection = None
    failed = False
    try:
        connection = http.client.HTTPSConnection("api.telegram.org", timeout=timeout)
        connection.request("POST", "/bot" + token + "/sendMessage",
                           body=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError()
        result = response.status, json.loads(raw)
    except Exception:
        failed = True
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass  # A close failure does not invalidate an already received response.
    # Outside the handler, no token-bearing exception context is retained.
    if failed:
        raise uncertain()
    return result


class TelegramClient:
    def __init__(self, config: TelegramConfig, *, request=_request, timeout=15):
        self._config = TelegramConfig(config.token, config.chat_id)
        self._request = request
        if type(timeout) not in (int, float) or not 0 < timeout <= 60:
            raise BridgeError("TELEGRAM_CONFIG", "Telegram timeout must be between 0 and 60 seconds.")
        self._timeout = timeout

    def send(self, text):
        if len(split_message(text)) != 1:
            raise BridgeError("INVALID_INPUT", "Send one bounded message at a time.")
        payload = {"chat_id": self._config.chat_id, "text": text,
                   "link_preview_options": {"is_disabled": True}}
        _require_quiet_http()
        failed = False
        try:
            status, body = self._request(self._config.token, payload, self._timeout)
        except Exception:
            failed = True
        if failed:
            raise uncertain()
        if type(status) is not int or not 100 <= status <= 599:
            raise uncertain()
        if type(body) is dict and body.get("ok") is False and type(body.get("error_code")) is int:
            code = body["error_code"]
            if code == 429:
                parameters = body.get("parameters")
                retry_after = parameters.get("retry_after") if type(parameters) is dict else None
                if type(retry_after) is not int or retry_after < 1:
                    retry_after = None
                raise DeliveryError("TELEGRAM_RATE_LIMIT", "Telegram rate-limited this message; no retry was made.",
                                    retry_after=retry_after)
            if code in (401, 403):
                raise DeliveryError("TELEGRAM_AUTH", "Telegram rejected credentials or bot access; check token and blocking.")
            if code in (400, 404):
                raise DeliveryError("TELEGRAM_CHAT", "Telegram rejected the destination or request; check private chat setup.")
            raise DeliveryError("TELEGRAM_REJECTED", "Telegram explicitly rejected the request; no retry was made.")
        result = body.get("result") if type(body) is dict else None
        if (type(status) is not int or not 200 <= status < 300 or type(body) is not dict or body.get("ok") is not True or type(result) is not dict or
                type(result.get("message_id")) is not int or result["message_id"] < 1 or
                type(result.get("chat")) is not dict or
                type(result["chat"].get("id")) is not int or
                str(result["chat"].get("id")) != self._config.chat_id or
                result["chat"].get("type") != "private" or result.get("text") != text):
            raise uncertain()
        return {"accepted": True}


def send_once(text, *, execute=False, env=None, client_factory=TelegramClient):
    if type(execute) is not bool:
        raise BridgeError("INVALID_INPUT", "execute must be a boolean.")
    chunks = split_message(text)
    if not execute:
        return {"outcome": "dry_run", "requests": 0, "planned_messages": len(chunks), "text": text}
    config = TelegramConfig.from_env(os.environ if env is None else env)
    # Validate diagnostic settings before the first request.
    _require_quiet_http()
    client = client_factory(config)
    confirmed = 0
    for chunk in chunks:
        try:
            receipt = client.send(chunk)
            if type(receipt) is not dict or receipt.get("accepted") is not True:
                raise uncertain()
            confirmed += 1
        except Exception as error:
            safe = (DeliveryError(error.code, uncertain=error.uncertain, retry_after=error.retry_after)
                    if isinstance(error, DeliveryError) else uncertain())
            return {"outcome": "partial" if confirmed else "unknown" if safe.uncertain else "rejected",
                    "confirmed_messages": confirmed, "total_messages": len(chunks),
                    "attempted_messages": confirmed + 1,
                    "failed_message": confirmed + 1, "current_message_uncertain": safe.uncertain,
                    "unattempted_messages": len(chunks) - confirmed - 1,
                    "retry_safe": False, "error": safe.public()}
    return {"outcome": "accepted", "confirmed_messages": confirmed, "total_messages": len(chunks),
            "attempted_messages": len(chunks), "retry_safe": False,
            "message": "Telegram accepted the messages. Recipient viewing and exactly-once delivery are not guaranteed."}
