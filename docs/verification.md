# Verification checklist

Documentation/source review date: **2026-10-25**. Automated checks use synthetic data and mocked adapters/HTTP. No Things item was mutated and no Telegram API request or real send was made during this work. Official documentation and dependency downloads were external requests.

| Check | Evidence / next action |
| --- | --- |
| No credentials or personal task data in publishable files | Ignore rules, placeholder-only .env.example, synthetic fixtures, local diff/content review. The lightweight pattern check is not a comprehensive secret scanner. |
| MCP starts correctly | Production entry point initialized and listed 7 tools with no tool calls; fake subprocess tests cover tool calls and output separation. Neither establishes Things permission or reads. |
| Read-only mode rejects live-write requests | Every mutation handler and adapter/transport gates tested with fakes. Default is disabled. |
| Previews do not mutate | All three mutation contracts tested with opt-in both off and on. Existing-task previews can read their target. |
| Controlled write test remains user-invoked | [Disposable-task procedure](manual-write-test.md), never run here. Live existing-task writes remain blocked. |
| Digest preview makes no Telegram request | Fake and live-read orchestration tests inject forbidden senders. The “live-read” unit test uses a fake service. |
| Real sending requires explicit execution | send-once defaults to dry_run; only --execute requests delivery. No token or destination CLI arguments. |
| Telegram errors are safe | Mock authentication, bad-chat, rate-limit, invalid response, timeout, split-message partial delivery, and secret-in-traceback tests. |
| Shortcuts variable selections are explicit | [Guide A/B](iphone-shortcuts.md) distinguishes literals, tokens, Title/ID properties and the selected whole Item. |
| Completion receives only the chosen item | Single selection, count equals one, cancelable confirmation, then Edit Items with SelectedTask. Requires a user-run disposable-task check. |
| Phone automation has a locked-device test | Separate manual and locked tests documented. Neither has been run on an iPhone. |
| Phone Telegram length and receipt checks precede task delivery | Offline Base64 preflight and synthetic send procedure in [Guide C](iphone-telegram.md). Device tests pending; Python tests do not validate Shortcuts wiring. |
| No duplicate daily sender is enabled | No scheduler or phone automation was installed here. User must inspect their own automations before enabling one sender. |

Run from the repository root:

    uv run --frozen python -m unittest discover -s tests -v
    uv run --frozen python -m compileall -q src/things3_everywhere tests scripts
    uv run --frozen python scripts/check_docs.py
    git diff --check

The standard suite includes a macOS-only test of pure AppleScript JSON/date helpers using synthetic content; it does not contact Things. These tests do not validate the full script against an installed Things dictionary.

## Integration checks still required

On a Mac with Things installed, inspect its dictionary, run doctor, grant only Automation permission if desired, and run counts-only Today/Inbox reads. Compare actual list semantics privately. Confirm supported fields, tags, localization and permission errors. List names currently assume English Things. Recurrence, start-date handling and deadline clearing remain unsupported until safely established; do not infer Cloud sync from local success.

On iPhone, build the native shortcut, check the filter and variable selections, exercise populated/empty states, then perform the separate locked-phone test. Test cancellation before trying completion on the user-identified disposable non-repeating task. Test optional Telegram with synthetic text only after the offline length preflight and review of the fixed destination and privacy boundary. Confirm malformed/mismatched receipts cannot reach the success notification. Inspect existing automations yourself; this review cannot determine whether another phone or Mac already sends your briefing.

Record the iOS/Things versions and pass/fail outcomes privately, without titles, IDs, tokens, response dumps, or screenshots. Calendar overlap/all-day behavior remains unverified and separate. See the [Tranche 03 report](tranche-03-report.md) for the exact automated checks and source review.

## Scope and source notes

The [Mac setup](mac-setup.md), [Telegram guide](telegram-setup.md), [iPhone guide](iphone-shortcuts.md), and [phone Telegram guide](iphone-telegram.md) contain primary-source links. Corrections to common assumptions: native Open List is not a task query; start-date-only filters are not a complete Today list; native Edit Items is not undoable; repeating early-start deadline properties can differ from final deadlines; a timeout can follow successful delivery.
