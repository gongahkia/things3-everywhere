# Things3 Everywhere

A bridge from supported Things 3 automation to other interfaces. Things remains
the task manager. This is an independent project, not an official Cultured Code
product.

Choose a starting point:

| Workflow | Guide | Status |
| --- | --- | --- |
| iPhone-only local briefing and manual completion | [iPhone Shortcuts](docs/iphone-shortcuts.md) | Official documentation checked; device testing required. No Mac needed. |
| Mac-local Codex/MCP | [Mac setup and tool contract](docs/mac-setup.md) | Implemented; synthetic tests pass. Things app unavailable on the development Mac. |
| Mac digest preview and explicit Telegram send-once | [Digest and Telegram](docs/telegram-setup.md) | Implemented; HTTP tests are mocked. No real send performed. |
| Telegram directly from iPhone | [Phone delivery](docs/iphone-telegram.md) | Optional manual setup guide; not installed or device-tested. |

**Start on iPhone:** build Guide A, run it manually, then perform its locked-phone
test before choosing an 8:30 AM Singapore automation. No repository install or
Mac is needed. Manual task completion and Telegram delivery are separate opt-ins.
The guides record their official-source review date and remaining device checks.

The Mac implementation uses AppleScript for actual Today/Inbox lists, bounded
title search, and stable-ID lookup. Seven MCP tools also expose create, update
and complete contracts. Creation has a guarded execution path and read-back;
**live update and completion remain blocked** because the supported interface
cannot establish recurrence safety. Start-date writes and deadline clearing are
unsupported. See the [upstream investigation](docs/upstream-review.md) for the
inspected revisions and original-adapter decision; neither candidate is adopted.

The deterministic digest preserves Today ordering, excludes notes, flags capped
results, and defaults to Asia/Singapore. Its local preview never calls Telegram.
The optional sender targets one configured private chat, defaults to dry run,
and requires explicit **--execute**. The phone briefing uses accurately labeled
date filters; it does not claim to retrieve the complete Today list.

For a first local run from this repository (Python environment managed by uv):

    uv sync --frozen
    .venv/bin/things3-everywhere digest preview --fake
    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere doctor

For read-only Codex registration, after setup:

    codex mcp add things3-everywhere --env THINGS_ALLOW_WRITES=false -- "$PWD/.venv/bin/things3-everywhere-mcp"

Registration is user-run; this project does not change Codex configuration.
[Official Codex MCP instructions](https://developers.openai.com/codex/mcp).

Things writes are disabled by default and require both process opt-in and an
explicit execution choice. Previews stay non-mutating even with opt-in.
[Controlled disposable-task test](docs/manual-write-test.md). Only Automation
permission is needed for live Mac access; there is no database fallback, Cloud
credential request, or sync engine. Things Cloud sync has not been verified.
Task content returned to Codex or sent to Telegram leaves the local-only privacy
boundary. Configuration, exports, logs, and credentials must stay private.

No remote ChatGPT access, Telegram reply editing, polling, webhook, public
listener, automatic scheduling, or calendar integration is implemented. The
phone guides require manual setup and separate locked-device tests. Enable only
one daily sender initially. See the [verification checklist](docs/verification.md).
Calendar integration and a Mac scheduler remain future work; the optional calendar
appendix is an unverified specification. See the [setup review](docs/tranche-03-report.md)
for what was checked, corrected, and left for manual testing.

Run the automated checks:

    uv run --frozen python -m unittest discover -s tests -v
    uv run --frozen python -m compileall -q src/things3_everywhere tests scripts
    uv run --frozen python scripts/check_docs.py

To remove the MCP registration, run **codex mcp remove things3-everywhere**.
Stop invoking the sender and remove its private credentials to disable delivery;
turn off any phone automation you created. No daemon is installed. No project
licence has been selected.
