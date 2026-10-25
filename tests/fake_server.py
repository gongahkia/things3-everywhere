"""Subprocess fixture: always synthetic, never selectable by production config."""

import logging
import os
import sys

import anyio

from things3_everywhere.safety import WritePolicy
from things3_everywhere.server import configure_logging, serve
from things3_everywhere.service import ThingsService
from test_service import FakeAdapter, sample

enabled = os.environ.get("TEST_ENABLE_FAKE_WRITES") == "true"
adapter = FakeAdapter([sample(), sample("synthetic-b")], enabled=enabled)
configure_logging()
logging.warning("PRIVATE_LOG_SENTINEL with notes and arguments %r", {"notes": "secret synthetic notes"})
anyio.run(serve, ThingsService(adapter, WritePolicy(enabled)))
if not enabled and adapter.writes:
    sys.exit(5)

