# Tranche 01 completion report

Date: 2026-10-25. Work was performed in the standalone
`gongahkia/things3-everywhere` clone. Its initial working tree was clean and
contained only a README. No applicable AGENTS.md was found in the repository or
ancestor locations. No files from the separate migration project were read,
copied, edited or imported.

## Implementation

- Original AppleScript adapter with JSON input over stdin, stable-ID reads,
  actual Today/Inbox lists, bounded open-title search, sanitized errors and
  subprocess timeouts. No Things database access, fallback or Cloud protocol.
- Shared validation, write policy and service for CLI, MCP and future clients.
  Preview is the per-call default; global opt-in alone cannot execute a write.
  Creation dispatches once and requires an independent read-back before success.
- Update/completion service logic targets one ID, preserves omitted fields,
  rejects unsafe recurrence, and verifies the resulting state. **The live
  AppleScript adapter blocks every existing-task mutation**, since recurrence
  detection could not be established. Those execution paths were tested on fakes.
- Seven structured stdio MCP tools, a local JSON CLI and a task-free diagnostic.
  No HTTP listener, background daemon, scheduler or LLM dependency.
- Public-repository ignore rules, frozen dependency lock, setup instructions,
  limitations and a manual disposable-task test. No project licence was invented.

## Upstream choice

No upstream project was adopted or copied. Reviewed documentation and relevant
source at:

- Schimmilab: `13c6b42b7cc5706ac1fade98ae4d9384eff090e8`.
- than: `c7cfb0094db774d12dc88a91f0dcff244e0ae83d`.

Both were MIT licensed at those revisions. First-title/bulk mutation and missing
verification ruled out the former as-is; automatic database access ruled out
the latter. See [the detailed review](upstream-review.md) for inspected paths,
attribution obligations, runtime requirements and risk findings.

Dependencies used directly: `mcp==1.28.0`, `anyio==4.15.1`,
`jsonschema==4.26.0`. All runtime transitive versions/hashes are locked in
`uv.lock`. Build backend: `hatchling==1.32.4`. Tested interpreter: Python 3.11.16
selected by uv 0.12.6. No candidate upstream was executed.

## Files belonging to this tranche

- `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock`, `README.md`.
- `src/things3_everywhere/`: `__init__.py`, `adapter.py`, `cli.py`, `errors.py`,
  `model.py`, `runtime.py`, `safety.py`, `server.py`, `service.py`, `tools.py`,
  `transport.py`, `validation.py`, `things.applescript`.
- `tests/`: `test_service.py`, `test_adapter.py`, `test_protocol.py`,
  `fake_server.py`.
- `docs/upstream-review.md`, `docs/manual-write-test.md`, this report.

Separate interface work appeared concurrently during development, initially as
JavaScript files and later as additional Python modules and CLI changes. That
work was not adopted, edited or committed by this tranche. Its `.env.example`
and concurrent `.gitignore` edit were also left alone. A shared test discovery
run also picked up 19 concurrent tests (52 passed in total); those are not claimed
as this tranche's coverage. Final tranche validation uses an isolated committed
snapshot with only its 33 tests. The shared working tree is therefore not clean
even though this tranche's changes are committed. Do not blanket-stage the
remaining files as part of this tranche.

## Checks actually performed

| Check | Result and scope |
| --- | --- |
| `uv sync --frozen` / locked environment | Dependencies resolved and installed; no Things access. |
| `uv run --frozen python -m unittest discover -s tests -v` | **33 tranche tests passed**, also verified in an isolated committed snapshot using the locked interpreter/environment. Synthetic service/adapter data and mocked subprocesses; real stdio protocol tests use an isolated fake server. |
| Synthetic AppleScript helper/gate tests | Passed on macOS. Execute only Foundation JSON/calendar helpers and the extracted production write gate; no Things clause or mutation code is included. |
| `uv run --frozen python -m compileall -q src/things3_everywhere tests` | Passed. Python syntax only. |
| `uv build --wheel` | Passed. Wheel includes the fixed AppleScript resource and only the Python tranche package. |
| Production stdio entrypoint smoke | Initialization, seven-tool listing and synthetic creation **preview** passed with writes disabled; server exited cleanly with no stderr output. No Things call was needed. |
| App discovery | Spotlight bundle-ID lookup and app metadata checks under system/user Applications found no Things app. |
| `things3-everywhere doctor` | Returned `APP_NOT_FOUND`, writes disabled, Cloud sync unverified. |
| Read-only `things_today --summary` attempt | Returned `APP_NOT_FOUND` before AppleScript task execution. No task contents retrieved. |
| Codex CLI registration help | `codex mcp add --help` / `remove --help` inspected alongside current official docs. No registration/configuration change made. |
| Diff and public-data review | Reviewed tranche-owned source/docs and locked URLs; no real task contents, credentials, exports, database files or machine-specific configuration included. `git diff --check` passed. |

Coverage includes every mutation gate, preview under both policies, duplicate
titles with stable IDs, Unicode/quotes/backslashes/multiline and separator
characters, empty/missing results, date validation, omitted-field preservation,
explicit notes/tag clearing, replacement, permission failures, timeouts,
unverifiable and ambiguous writes, recurrence changes, and MCP stdout/stderr
separation. Tests also reject unexpectedly changed omitted fields. They do not
prove how Things itself behaves.

**No real Things item was created, edited, completed or deleted. No successful
live task read, installed Things dictionary inspection, permission prompt test,
or Things Cloud sync test was possible.**

## Remaining limits

- Actual Things scripting dictionary and complete script compilation/execution
  must be checked on a Mac with Things installed. Pure helper execution is not a
  substitute for that integration test.
- Existing-task mutation is blocked due to unknown recurrence. No bypass flag.
- Start dates and deadline clearing are unsupported; notes/tags clear explicitly.
  No checklist, heading, container, recurrence, delete or bulk tools.
- Search covers open titles only, returns at most 100 items, and has no pagination.
  Large app queries may time out even though serialized results are capped.
- Apple Events are not a transaction. Partial creation, app normalization or
  concurrent user/Cloud edits may prevent read-back verification. No retry,
  rollback or cross-device consistency guarantee is provided.
- Task text intentionally returned by tools reaches the MCP client. Logs and
  summaries suppress that content; the bridge cannot control client retention.

## Run and registration commands

From the repository root:

```sh
uv sync --frozen
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere doctor
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere call things_today --summary </dev/null
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere-mcp
```

The last command starts the interactive stdio server; stop it with Ctrl-C.
Register separately when ready:

```sh
codex mcp add things3-everywhere --env THINGS_ALLOW_WRITES=false -- "$PWD/.venv/bin/things3-everywhere-mcp"
codex mcp list
```

Remove with `codex mcp remove things3-everywhere`. Registration syntax follows
[official OpenAI documentation](https://developers.openai.com/codex/mcp).

## Smallest later write test

You explicitly choose a unique disposable task title, preview creation with
writes disabled, then execute **once** using both the process opt-in and
`execution: "execute"`. Inspect the returned stable ID and the task in Inbox.
If uncertain, inspect before any retry. Cleanup is manual in Things. Full
commands and prerequisites are in [the manual procedure](manual-write-test.md).
Live update/completion tests remain unavailable until recurrence can be verified.
