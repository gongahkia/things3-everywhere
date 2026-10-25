# Things3 Everywhere

Documentation checked **2026-10-25**. This is the detailed Mac-local foundation
guide; return to the [project overview](../README.md) to choose another workflow.
For the new digest commands, see [digest and Telegram setup](telegram-setup.md).

A local bridge to Things 3 through supported automation interfaces. Tranche 01
provides a reusable Python adapter, a CLI, and a local stdio MCP server for Codex.
It is not an independent task manager or an official Cultured Code product.

**Writes are disabled by default. No live Things writes were performed during
development.** The machine used for this tranche has macOS but no discoverable
Things installation, so Things-specific AppleScript execution remains unverified.

Seven tools cover Today, Inbox, title search, get-by-ID, create, update and
complete. All write tools default to previews. Creation has a guarded execution
path with read-back verification. **Live update and completion are blocked**:
the reviewed AppleScript interface cannot establish recurrence safety. Their
shared service contracts are implemented and tested with fakes. There is no
override that asserts a real task is nonrepeating.

## Local setup and read-only use

Requires macOS and Things 3 for live access. The locked development runtime is
Python 3.11.16 (`.python-version`); the package supports Python >=3.11. Install
[uv](https://docs.astral.sh/uv/) if needed, then run from this repository:

```sh
uv sync --frozen
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere doctor
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere call things_today --summary </dev/null
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere call things_inbox --summary </dev/null
```

`doctor` checks app metadata and the scripting dictionary without reading tasks.
It exits nonzero if unavailable. `--summary` prints only counts/outcomes. Omit it
only when you want task content displayed. Task content returned through MCP is
available to its client/model; keep diagnostics and transcripts private.

The adapter looks for `Things3.app` or `Things.app` in `/Applications` and
`~/Applications`. For another location, set `THINGS_APP_PATH` to the absolute app
bundle path. It checks the bundle ID. No `.env` file is loaded automatically.

On the first live read, macOS may request **Automation → Things** permission for
the app launching the server. Grant only that permission if you want live access.
No Full Disk Access, Accessibility permission, URL token or Cloud credentials are
needed. Permission denial is an error; there is no fallback or permission bypass.

Before a first live integration test, inspect the installed dictionary in Script
Editor → File → Open Dictionary → Things, or run `sdef` on its app bundle. The
diagnostic checks required term names; it does not prove operational semantics.

## Codex registration

After `uv sync --frozen`, from the repository root:

```sh
codex mcp add things3-everywhere --env THINGS_ALLOW_WRITES=false -- "$PWD/.venv/bin/things3-everywhere-mcp"
codex mcp list
```

The shell expands `$PWD` to an absolute executable path. This syntax was checked
against [official OpenAI MCP documentation](https://developers.openai.com/codex/mcp)
and local CLI help. Registration is a command for you to run; development did not
change global Codex configuration. Restart the client/session after configuration
changes; `/mcp` shows active MCP servers in the Codex terminal UI.

For a direct stdio launch:

```sh
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere-mcp
```

This waits for MCP protocol messages on stdin. It opens no network listener.
Stdout contains only protocol traffic; redacted diagnostics use stderr.

## Tool contract

| Tool | Input and behavior |
| --- | --- |
| `things_today` | Actual Things Today list; `limit` 1–100, default 50; `include_notes` default false. |
| `things_inbox` | Actual Inbox, same result options. |
| `things_search` | Required `query`; matches open task titles with Things' AppleScript `contains` semantics. Same result options. No notes, completed-task or Logbook search. |
| `things_get_task` | Required stable `id`; includes notes. Missing ID returns `NOT_FOUND`. |
| `things_create_task` | `fields` object, required title; optional `execution: "preview"` or `"execute"`. Creates one ordinary task in Inbox. |
| `things_update_task` | Required stable `id` and nonempty `fields`; preview available, live execution blocked by recurrence safety. |
| `things_complete_task` | Required stable `id`; preview available, live execution blocked by recurrence safety. |

List results contain `tasks`, `count` (returned count), `limit`, and `has_more`.
No total inventory or pagination is exposed. Things selects matching task
references before the cap is applied; at most 100 records are serialized. Large
libraries can time out. Use a narrower search; no automatic retry occurs. Order
and text matching follow Things, not a separately implemented search index.

Task fields: `id`, `title`, `notes` when requested, `tags`, `deadline` (ISO date or
null), `status` (`open`, `completed`, `canceled`), and `recurrence` (`unknown` for
this live adapter). A missing start-date field means unsupported, not unscheduled.

| Writable field | Semantics |
| --- | --- |
| `title` | Nonblank text, at most 500 characters. Replacement only; cannot clear. |
| `notes` | Text, at most 20,000 characters. Replacement only; `""` explicitly clears. |
| `tags` | At most 25 distinct existing names, each at most 80 characters. Replacement only; `[]` explicitly clears. Commas, newlines and surrounding whitespace are rejected. Missing or ambiguous tag names reject creation before dispatch. |
| `deadline` | Valid `YYYY-MM-DD` local calendar date, maps to Things' `due date`. Not a start date. Clearing via null is explicitly unsupported pending verification. |

Omitted fields remain unchanged on updates. There is no append/merge mode.
`start_date`, recurrence, checklists, headings, project/area placement and all
other fields produce explicit errors. No deletes, bulk mutations, template
changes, arbitrary script/shell execution, or database access are exposed.

## Write safety

Live creation needs **both** `THINGS_ALLOW_WRITES=true` on the launching process
and `execution: "execute"` on that individual call. The exact string `true` is
required; other values fail closed. A global opt-in never changes preview
behavior. The service, adapter, transport, and AppleScript creation handler each
enforce their write gate. Future interfaces must call the shared service.

Results distinguish `preview`, `verified`, `accepted_unverified` and `unknown`.
Errors include a fixed code/message and outcome. A preview validates the request;
it does not prove permissions, tag existence, or the ability to execute later.
The service reads the affected stable ID after dispatch and compares the
expected state, including unchanged exposed fields for updates. It does not
claim verified success from a subprocess exit code alone.

No write is retried automatically. A timeout, process failure, invalid receipt,
partial write or failed read-back can leave an uncertain result. Inspect Things
before a manual retry; this bridge offers no rollback or transaction with Things.
Other apps and Cloud sync can change tasks between calls. Cloud sync was not
tested and is not a success criterion for local verification.

Use the [manual disposable-task procedure](manual-write-test.md) only when
you explicitly choose to test a real write later. Leave Codex registered with
writes disabled during that separate CLI test.

## Architecture and verification

| Location | Responsibility |
| --- | --- |
| `src/things3_everywhere/adapter.py`, `transport.py`, `things.applescript` | Supported AppleScript adapter; fixed source, JSON data on stdin, bounded subprocess timeouts, sanitized errors. |
| `model.py`, `validation.py`, `safety.py`, `service.py` | Reusable task model, validation, policy, preview/execute handling and read-back verification. |
| `tools.py`, `server.py` | Seven MCP schemas/handlers and stdio transport using the official MCP SDK. |
| `cli.py`, `runtime.py` | Local diagnostics, calls, and environment wiring. |
| `tests/` | Synthetic adapter, subprocess and MCP protocol tests. Never real Things tasks. |

The MCP SDK is pinned to `mcp==1.28.0`; all resolved dependencies and hashes are
in `uv.lock`, and the build backend is pinned. The SDK brings transitive web
packages, but this project starts only stdio. The foundation starts no web server, scheduler, daemon, sync engine, or replacement task store. The optional digest sender added in tranche 02 is an explicitly invoked outbound client; see [digest and Telegram setup](telegram-setup.md).

```sh
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python -m compileall -q src/things3_everywhere tests
```

See [the upstream review](upstream-review.md) for exact inspected revisions,
licence findings and the decision to write an original adapter. Neither upstream
is a dependency and no upstream source or database fixture was copied. No project
licence has been selected. See [the tranche report](tranche-01-report.md) for
checks actually performed and remaining integration gaps.

## Disable or remove

Keep `THINGS_ALLOW_WRITES=false` and restart the server/client to ensure a
previous process with opt-in has exited. To disable the MCP entry without
removing it, set `enabled = false` under its existing `mcp_servers` entry in your
Codex configuration. To remove it:

```sh
codex mcp remove things3-everywhere
```

Stop any manually launched stdio process with Ctrl-C. If desired, revoke the
launching app's Things Automation permission in System Settings. There is no
daemon to uninstall and no task database to migrate.
