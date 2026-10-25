# Digest, Telegram and iPhone setup completion report

Date: **2026-10-25**. Repository: **gongahkia/things3-everywhere**.

The repository initially contained only its README. While this session was implementing the foundation, another process created and committed a Python foundation in the same working tree. This session did not stage, commit, push, reset or discard changes. It inspected and preserved that foundation, then used its shared service for digest reads. The earlier Node draft was preserved under ignored local storage and is not a second shipped adapter. Concurrent changes to ignore rules and runtime were preserved. A further external commit, a884299, included the implementation and additional safety tests during final verification.

## Delivered

- Deterministic pure Today formatter: Singapore default, configurable IANA timezone, stable-ID deduplication, source ordering, empty/partial states, no notes, and conservative deadline handling.
- CLI local preview and explicit Telegram send-once, defaulting to dry run. Digest services force Things writes off, even if the surrounding environment opted in.
- Small standard-library HTTPS client: one configured private destination, explicit timeout, Unicode code-point-preserving splitting, response verification, sanitized failures, rate-limit reporting, no redirects/retries, and partial/uncertain delivery results.
- iPhone-only native Shortcuts briefing, controlled single-item completion, optional direct Telegram delivery, manual and locked-device tests, and a clearly unverified calendar appendix.
- Focused README with separate workflow routes, detailed setup guides, placeholder-only environment example and verification checklist.

## Files added or changed by this continuation

Added: **.env.example**; **src/things3_everywhere/briefing.py**, **digest.py**, **telegram.py**; **tests/test_digest.py**, **test_telegram.py**, **test_briefing_cli.py**; **scripts/check_docs.py**; **docs/mac-setup.md**, **telegram-setup.md**, **iphone-shortcuts.md**, **iphone-telegram.md**, **verification.md**, and this report.

Changed: **README.md**, **src/things3_everywhere/cli.py**, and a link in **docs/manual-write-test.md**. Additional concurrent improvements to the shared runtime, formatter and Telegram safety handling were reviewed and included in combined verification. Existing ignore-rule changes were retained.

## Investigation and corrections

Neither upstream was adopted or copied. Inspected revisions were Schimmilab **13c6b42b7cc5706ac1fade98ae4d9384eff090e8** and than **c7cfb0094db774d12dc88a91f0dcff244e0ae83d**. Both were MIT; the [upstream review](upstream-review.md) records licence obligations and rejected safety behaviors. No project licence was selected.

Official sources checked include [Things' supported interfaces](https://culturedcode.com/things/support/articles/5510170/), [AppleScript](https://culturedcode.com/things/support/articles/4562654/), [Shortcuts actions](https://culturedcode.com/things/support/articles/9596775/), [the Shortcuts announcement](https://culturedcode.com/things/blog/2023/01/shortcuts-reloaded/), [Apple's guide](https://support.apple.com/guide/shortcuts/welcome/ios), [Telegram Bot API](https://core.telegram.org/bots/api), [BotFather](https://core.telegram.org/bots/features#botfather), and [Codex MCP](https://developers.openai.com/codex/mcp). Specific Apple variable, notification, alert, HTTP and automation pages are linked in the guides.

Corrections: Open List displays a Things list but is not a task query; native date filters do not constitute the complete Today list; Edit Items cannot be undone; early-start repeating deadline fields can differ from final deadlines. Date-filter equality uses is Today rather than an invented date range. API acceptance, verified response state, recipient viewing and exactly-once delivery are different claims.

## Checks actually run

- Python foundation baseline: 29 tests passed at first inspection; further concurrent foundation tests were preserved.
- Combined final suite at this report's snapshot: **72 tests passed**, including the concurrent safety tests, with synthetic tasks and mocked Telegram transport.
- Python compileall, documentation link/fence/environment/token-pattern checks, and git diff --check passed.
- Production stdio entrypoint initialized, listed seven tools, returned a synthetic creation preview, and exited cleanly at EOF with no stderr output. No Things task access was required.
- Doctor and a counts-only Today read attempt returned **APP_NOT_FOUND** before task scripting. No task contents were retrieved.
- Fake digest preview and fake send-once dry run returned **requests: 0**.
- The suite executed pure macOS AppleScript JSON/date and extracted gate checks with synthetic data; it did not execute a Things mutation.

Research and dependency downloads made external requests. **No Telegram Bot API request, real message, real Things mutation, global Codex configuration change, public endpoint or scheduler installation occurred in this session.** No iPhone hands-on test was performed.

## Remaining manual checks

The installed Things dictionary, complete script compilation, Automation permission and live read behavior still require a Mac with Things. Existing-task writes remain blocked for unknown recurrence; start-date writes and deadline clearing are unsupported. Digest reads cap at 100; unknown recurrence causes deadline omission. English built-in list names are assumed. Things Cloud sync is unverified.

The phone instructions require on-device construction, variable/filter inspection, unlocked and locked tests, and a disposable non-repeating completion test. The Telegram client needs a later explicitly chosen synthetic send. Calendar behavior remains unverified and separate.

## Shortest first use

From the repository root:

    uv sync --frozen
    .venv/bin/things3-everywhere digest preview --fake
    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere doctor
    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere call things_today --summary </dev/null
    THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest preview

After Mac setup, register read-only:

    codex mcp add things3-everywhere --env THINGS_ALLOW_WRITES=false -- "$PWD/.venv/bin/things3-everywhere-mcp"

Remove with **codex mcp remove things3-everywhere**. Registration syntax was checked against official docs and local CLI help; registration was not performed.

For phone-only use, begin with [Guide A](iphone-shortcuts.md), run manually, then test while locked before keeping a daily trigger. Only one daily sender should be enabled.

The smallest later Things write is one user-identified disposable creation, previewed first and executed once using both explicit controls in the [manual write procedure](manual-write-test.md). Cleanup is manual. A later synthetic Telegram delivery uses **digest send-once --fake --execute** only after private configuration and destination review in [Telegram setup](telegram-setup.md).
