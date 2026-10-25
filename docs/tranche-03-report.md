# Tranche 03 — iPhone Shortcuts and setup review

Review date: **2026-10-25**. Repository confirmed as `gongahkia/things3-everywhere`.
No applicable repository instructions were found. Existing changes were preserved;
nothing was staged, committed, pushed, reset, cleaned, or discarded.

## Documentation changed

| File | Result |
| --- | --- |
| `README.md` (historical; removed in a later revision) | Phone-first starting sequence; links distinguished implemented Mac features, phone recipes, and future work. |
| [iPhone Shortcuts](iphone-shortcuts.md) | Current requirements, explicit variable/property selection, read-only date-filter briefing, daily 8:30 AM setup and locked-phone test, single selected-item completion with cancellation. |
| [Phone Telegram](iphone-telegram.md) | Private setup, explicit request/receipt variable wiring, standalone synthetic send test, offline Unicode/length preflight, fixed destination and error/privacy limitations. |
| [Verification checklist](verification.md) | Selected-item guard and phone delivery preflight checks; distinction between Python tests and pending device verification. |
| This report | Sources, corrections, checks, and shortest first-use sequence. |

No implementation, dependency, or test code changed. The existing adapter and
MCP service were usable for fake-backed checks and protocol startup. Live Things
access remains blocked by the absent app. Pre-existing changes in
`docs/telegram-setup.md`, `docs/tranche-02-report.md`, and
`docs/tranches-02-03-report.md` were left intact.

## Primary sources checked

- [Things Shortcuts technical reference](https://culturedcode.com/things/support/articles/9596775/): action names, item/list types, filters, edit behavior, date and repeating-task caveats.
- [Things Shortcuts launch article](https://culturedcode.com/things/blog/2023/01/shortcuts-reloaded/): historical launch requirements, distinguished from the current technical reference.
- [Apple Shortcuts guide](https://support.apple.com/guide/shortcuts/welcome/ios), including [variables](https://support.apple.com/guide/shortcuts/apda36b9018b/ios), [list selection](https://support.apple.com/guide/shortcuts/use-list-actions-apd4dcacc115/ios), [notifications](https://support.apple.com/guide/shortcuts/use-the-show-notification-action-apd2175adcab/ios), and [cancelable alerts](https://support.apple.com/guide/shortcuts/use-the-show-alert-action-apdb9661c761/ios).
- Apple [automation creation](https://support.apple.com/guide/shortcuts/apdfbdbd7123/ios), [event triggers](https://support.apple.com/guide/shortcuts/apd932ff833f/ios), and [automatic execution](https://support.apple.com/guide/shortcuts/apd602971e63/ios). Pages can serve different OS versions/localizations; match the installed version.
- Apple [HTTP requests and JSON bodies](https://support.apple.com/guide/shortcuts/apd58d46713f/ios) and [dictionary extraction](https://support.apple.com/guide/shortcuts/get-dictionary-value-action-apdf01294032/ios).
- Telegram [BotFather](https://core.telegram.org/bots/features#botfather) and [Bot API](https://core.telegram.org/bots/api), particularly getUpdates, sendMessage, and response parameters.

This is documentation-based verification. No iPhone was connected, shortcut
installed, or downloadable `.shortcut` produced. Existing Codex registration
instructions retain their Tranche 01 verification; this review did not register
an integration or change Codex configuration.

## Corrections and retained boundaries

- The launch article's iOS 16 requirement is historical. The current Things
  action reference lists Things 3.17 and iOS 17 as minimums.
- Removed an unconfirmed claim about an iOS 27 **Edit → Automation** menu and
  a specific locked-running setting. The retrieved Apple setup pages describe
  the Automation-tab flow. Locked execution requires its own test.
- Native Open List displays Today; it is not an item query. The phone guide
  retains separate, accurately labeled start-date and deadline-field queries,
  excludes earlier dates, discloses limits, and includes a repeating-item caveat.
- Completion passes the chosen whole Item, checks the selection count, confirms
  its title/ID, and uses that reference for verification. Title text and the
  complete search result never become edit targets. Undo is not promised.
- Phone Telegram now checks a positive message ID, private chat, fixed destination,
  and returned text. It rejects long text rather than silently truncating it.
  The Base64 guard's mathematics was checked in Python; its Shortcuts behavior
  is explicitly pending an offline device preflight. iOS network errors do not
  inherit the Python client's redaction or timeout guarantees.
- Calendar overlap/all-day handling remains a separate, explicitly unverified
  appendix. No rescheduling recipe, recurring-template edit, reply handler, or
  scheduler was added.

## Checks actually executed

| Check | Result |
| --- | --- |
| `uv run --frozen python -m unittest discover -s tests -v` before changes | **72 passed**, no pre-existing failures. |
| `uv run --frozen python -m unittest discover -s tests -q` after changes | **72 passed**. |
| `uv run --frozen python -m compileall -q src/things3_everywhere tests scripts` | Passed. |
| Production `things3-everywhere-mcp` via a local stdio MCP client, writes disabled | initialize and tools/list succeeded; **7 tools**, no tool calls. Process stopped after the check. |
| `THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere doctor` | Expected integration limitation: **APP_NOT_FOUND**, exit 1. No task access attempted. |
| `THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest preview --fake` | Synthetic local preview, **0 requests**. |
| `THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere digest send-once --fake` | Synthetic dry run, **0 requests**, one planned message. |
| Synthetic Python UTF-8/Base64 calculations | A and emoji expectations, plus the 3001-byte rejection boundary, passed. This is not a phone test. |
| `uv run --frozen python scripts/check_docs.py` | Passed across **12 Markdown files**: relative links, fences, publishable environment files, and literal bot-token pattern. |
| `git diff --check` and content review | Passed; changes use synthetic examples. No credentials or personal task content found in the reviewed diff. |

The suite uses fake Things adapters and mocked Telegram HTTP, including mutation
gates, preview safety, receipts, ambiguous timeouts, protocol output, and private
error handling. Its pure macOS AppleScript helper tests do not invoke Things.

External requests were made to retrieve official documentation. No authenticated
Telegram API request, real Telegram message, live task read, or Things mutation
was performed. No scheduler, public endpoint, daemon, or phone automation was
installed. Publishable content uses synthetic examples; ignored private data was
not read. A pattern scan and diff review cannot prove an exhaustive absence of
secrets.

## Manual checks still needed

On iPhone: verify installed action labels and types, populated/empty results,
notification permissions and locked execution, cancellation, and the explicitly
identified non-repeating disposable-task completion. Optional Telegram requires
the offline length preflight, synthetic receipt/error checks, and a user-chosen
send to the fixed private chat. Review existing daily senders before enabling one.

On a Mac with Things installed: inspect its actual scripting dictionary, verify
Automation permission and counts-only reads, and compare list/field semantics.
The existing controlled creation test remains user-invoked. Live adapter update
and completion stay blocked by recurrence safety. Things Cloud sync is unverified.

## Shortest first use

1. On iPhone, build [Guide A](iphone-shortcuts.md) and run it manually with local
   notifications only. No Mac setup is required.
2. Check an empty and populated result, then test a temporary Time of Day trigger
   with the phone locked. Only then keep the daily 8:30 AM Singapore trigger.
3. Add manual completion or [Telegram](iphone-telegram.md) separately if wanted;
   begin with the disposable/synthetic tests. Enable one daily sender initially.

For the independent Mac route, follow [Mac setup](mac-setup.md); the first safe
CLI preview is `uv sync --frozen` followed by
`.venv/bin/things3-everywhere digest preview --fake`.
