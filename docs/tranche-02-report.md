# Tranche 02 — digest and Telegram delivery

Review date: 2026-10-25. Repository identity confirmed as
`gongahkia/things3-everywhere`. No applicable AGENTS.md was found.

## Baseline and preservation

The starting HEAD was `2297a3b`. Existing uncommitted work already included the
formatter, Telegram client, briefing CLI commands, example configuration, tests,
and setup guides. Those were inspected and extended using Tranche 01's single
adapter and service. No replacement adapter, task database or extra dependency
was introduced. **All 52 baseline tests passed**, with no pre-existing failures.

Concurrent work continued in this shared tree, including additional CLI tests
and documentation. HEAD advanced externally to `a884299` during this turn.
This turn performed no staging, commits, pushes, resets, cleaning or discards.
The external commit and other work were preserved.

## Result

- Pure deterministic formatter accepts a structured Today page and an explicit
  aware instant. Singapore is the default heading timezone; IANA timezone
  overrides are supported. Source order is retained and stable IDs deduplicate
  within the section, without collapsing separate tasks sharing a title.
- Empty and capped lists are labeled. Task notes, tags and IDs are excluded.
  Only validated dates with known nonrepeating semantics receive deadline
  labels; unsupported dates and recurrence are not invented. No upcoming scan
  or calendar data access was added.
- Fake previews, live reads with local preview, dry runs, and actual delivery
  have distinct source/outcome labels. Every production digest read uses the
  existing service with **Things writes forcibly disabled**.
- Telegram delivery requires `send-once --execute`, a bot token and one allowed
  private chat ID from environment configuration. No recipient or token CLI
  argument is accepted. Presence of credentials cannot enable delivery.
- The standard-library HTTPS client uses the fixed Telegram host, plain JSON,
  disabled link previews, explicit socket timeouts, bounded response reads and
  no redirects or automatic retries. Each response and receipt is validated
  before counting a message as accepted. Unicode code points are preserved
  across conservative 4096-UTF-16-unit chunks.
- Rate limits stop with a validated retry hint. Ambiguous failures and partial
  sequences report confirmed, attempted and unattempted messages. HTTP failures,
  descriptions and exceptions are replaced by fixed messages without leaking
  token-bearing URLs or their exception context.

The reviewed [official Telegram Bot API](https://core.telegram.org/bots/api)
documents the sendMessage text bound, JSON response contract and retry_after
field. [BotFather](https://core.telegram.org/bots/features#botfather) and
[getUpdates](https://core.telegram.org/bots/api#getupdates) informed the manual
setup guide. Setup inspection is user-run; no getUpdates client, incoming-message
handler, polling loop or webhook is part of the implementation.

## Files changed in this turn

Extended existing work:

- `src/things3_everywhere/runtime.py`: optional forced read-only composition.
- `src/things3_everywhere/briefing.py`: read-only service, option/date validation
  before live reads.
- `src/things3_everywhere/digest.py`: structured-input, Unicode and timezone
  validation; visible control-character handling.
- `src/things3_everywhere/telegram.py`: safe transport exceptions, canonical
  diagnostics, stricter receipts, attempt accounting and environment handling.
- `tests/test_telegram.py`: successful fake chunks now return explicit receipts.
- `docs/telegram-setup.md`: forced read-only behavior, failure/privacy semantics,
  attempt accounting and CLI exit statuses.

Added:

- `tests/test_digest_safety.py`.
- `tests/test_telegram_safety.py`.
- This report.

The existing CLI, `.env.example`, digest/client tests, README and other setup
guides were reused and preserved; concurrent changes to them are not presented
as exclusively authored by this turn.

## Commands

From the repository root, after `uv sync --frozen`:

```sh
# Synthetic preview, no Things or Telegram access.
.venv/bin/things3-everywhere digest preview --fake

# Actual Things Today read, local output only.
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest preview

# Live Things read, dry run with zero Telegram requests.
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest send-once

# A timezone override changes the heading, not Things' Today membership.
.venv/bin/things3-everywhere digest preview --fake --timezone UTC
```

For a **later, explicitly chosen user test**, configure the private bot and chat
as described in [Telegram setup](telegram-setup.md), inspect a fake dry run, then
run once:

```sh
.venv/bin/things3-everywhere digest send-once --fake
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest send-once --fake --execute
```

The execution command above was **not run** in this implementation. To send real
titles later, review a live local preview before deliberately omitting `--fake`.

## Verification

- Baseline: 52 tests passed before behavior changes.
- Final combined suite: **72 tests passed**, including all Tranche 01 tests,
  existing digest/client/CLI tests, concurrent additions, and 16 new safety tests.
- The Telegram tests use synthetic tokens and destinations and mock every HTTP
  connection/request. Tests exercising an execution path deliver only to fakes.
- Coverage includes empty/populated data, timezone boundaries, ordering and
  duplicate IDs, unreliable dates, long Unicode titles, notes exclusion, dry-run
  isolation, configuration, destination restrictions, response validation,
  authentication/chat errors, rate limits, ambiguous timeouts, partial delivery,
  redaction, and all three levels of the forced read-only policy.
- `uv run --frozen python -m compileall -q src/things3_everywhere tests scripts`
  passed.
- `uv run --frozen python scripts/check_docs.py` passed: 11 Markdown files
  checked for relative links/fences plus publishable env and token-pattern checks.
- `git diff --check` and `uv build --wheel` passed.
- Actual CLI smoke checks for fake preview, fake send-once dry run and a UTC
  override returned synthetic output with `requests: 0`.
- The task-free diagnostic returned `APP_NOT_FOUND` with writes disabled.
  No live task read or real send was attempted in this turn.

No credentials or live API responses are needed for tests.

## Requests, delivery and limitations

External requests in this turn fetched official Telegram documentation.
**No Telegram Bot API request or real message was sent. No Things item was
mutated.** No scheduler, launchd job, cron job, login item, listener or persistent
process was installed. No credentials or local delivery history were generated.

Live Things behavior and Telegram delivery remain unverified. Tranche 01 found
no Things installation, and this turn does not infer a successful integration
from fake tests. Today membership and source date-only values follow the Mac;
the configurable heading timezone does not alter that list. Current live
recurrence is unknown, so deadlines are conservatively omitted. Results cap at
100 and show a partial notice; there is no pagination or broader inventory scan.

Socket timeouts do not bound the total duration of a multi-message sequence.
Splitting preserves code points but can divide a joined emoji or combining
sequence across messages. A verified API response proves acceptance, not viewing
or exactly-once delivery. After uncertainty, inspect the chat before manually
retrying, and never blindly rerun an already partially accepted digest.

Real digest delivery sends task titles outside the device to Telegram and the
configured recipient. Keep configuration private. Use only one daily sender
(the iPhone workflow or a future Mac scheduler) unless duplicate briefings are
explicitly intended. Calendar events remain separate from Things tasks.
