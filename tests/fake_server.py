"""Subprocess fixture: always synthetic, never selectable by production config."""

import logging
import os
import sys

from unittest.mock import patch

from things3_everywhere.safety import WritePolicy
from things3_everywhere import server
from things3_everywhere.service import ThingsService
from test_service import FakeAdapter, sample


class FailOnWriteAdapter(FakeAdapter):
    """Count entry to a mutation method, even if it would reject internally."""
    mutation_attempts = 0

    def forbidden_mutation(self, *args, **kwargs):
        self.mutation_attempts += 1
        raise AssertionError("Read-only test reached an adapter mutation method")

    create_task = forbidden_mutation
    update_task = forbidden_mutation
    complete_task = forbidden_mutation


enabled = os.environ.get("TEST_ENABLE_FAKE_WRITES") == "true"
adapter_type = FakeAdapter if enabled else FailOnWriteAdapter
adapter = adapter_type([sample(), sample("synthetic-b")], enabled=enabled)
server.configure_logging()
sys.stderr.write("Synthetic MCP fixture: fake Things adapter; no Things access.\n")
logging.warning("PRIVATE_LOG_SENTINEL with notes and arguments %r", {"notes": "secret synthetic notes"})
try:
    # Exercise the production main/logging/stdio/SDK path. Only composition is fake.
    with patch.object(server, "live_service", return_value=ThingsService(adapter, WritePolicy(enabled))):
        server.main()
finally:
    if not enabled and (adapter.mutation_attempts or adapter.writes):
        sys.exit(5)

