# Upstream investigation — 2026-10-25

Decision: implement an original, small Python adapter over AppleScript and use
the official MCP Python SDK for stdio. Neither candidate is adopted, installed,
or executed. No candidate source, fixtures, database, or licence is vendored.
The repository's owner has not selected a project licence; this tranche does
not select one. Upstream MIT licences do not license this project's new code.

## Inspected revisions

| Candidate | Exact revision | Licence |
| --- | --- | --- |
| [Schimmilab/things3-mcp-server](https://github.com/Schimmilab/things3-mcp-server/tree/13c6b42b7cc5706ac1fade98ae4d9384eff090e8) | `13c6b42b7cc5706ac1fade98ae4d9384eff090e8` | MIT, copyright 2026 Jürgen Schilling |
| [than/things-mcp](https://github.com/than/things-mcp/tree/c7cfb0094db774d12dc88a91f0dcff244e0ae83d) | `c7cfb0094db774d12dc88a91f0dcff244e0ae83d` | MIT, copyright 2026 than |

Both licences permit reuse subject to retaining the copyright and permission
notice in copies or substantial portions. No code is reused, so no copied-code
notice is required. See each revision's `LICENSE` for the full terms.

## Schimmilab

Read `README.md`, `LICENSE`, `pyproject.toml`, `requirements.txt`, and all of
`src/things3_mcp_server/server.py` (especially `_run`, `_SERIALIZE`,
`get_todo`, `create_todo`, `_set_status`, `update_todo`, and `add_tags`).

- Python >=3.10; `fastmcp>=3,<4`; setuptools >=61.0. Dependency ranges are not
  reproducible pins.
- Reads and writes use `osascript`; no database access or fallback in the
  inspected source. Requires macOS, Things and Automation permission.
- Reads actual built-in lists. Fields include ID, name, notes, status, tags,
  deadline (`due date`), activation date, completion date, project and area.
  Writes cover title, notes, append-notes, tags, schedule, deadline, placement
  and status. Deadline is distinguished from scheduling in docs and code.
- Task strings use argv with fixed script fragments, not shell interpolation.
  Scope/status interpolation is allowlisted. This is a useful design direction.
- **Unsafe targeting for this project:** update chooses the first matching
  title, while complete/cancel can mutate every matching open task. A stable-ID
  option does not remove those alternate mutation paths.
- Subprocess timeouts exist, but raw AppleScript errors are returned and can
  expose content. Broad `try` blocks suppress individual property and lookup
  errors. Separator-based serialization can misparse task control characters.
- Create returns an ID; updates return a name; completion returns matched names.
  None verifies the resulting fields with an independent read. Multi-step
  writes can fail after partial mutation. No global read-only gate, explicit
  preview/execution choice, or recurrence guard.
- Empty strings often mean omission; this prevents explicit clearing of notes
  and tags. `deadline="none"` invokes `delete due date`; its README claims live
  verification, but that claim was not reproduced here.

## than

Read `README.md`, `LICENSE`, `pyproject.toml`, and
`src/things_mcp/{applescript,db,read_backend,runner,server,urlscheme,writes}.py`.
Reviewed file-tree metadata, but did not download/open any database fixture.

- Python >=3.11; `mcp>=1.28,<2`, `things.py>=1.0.1,<2`, pytest >=8 for dev,
  hatchling for builds. An upstream `uv.lock` exists; it is not adopted.
- Default `auto` read backend probes a SQLite database, prefers database reads
  when reachable, and falls back to AppleScript. Even AppleScript mode can read
  the write token from the database if `THINGS_AUTH_TOKEN` is absent.
  This directly conflicts with the no-database boundary.
- URL-scheme writes use percent encoding and subprocess argv rather than a
  shell. Token redaction exists. AppleScript ID interpolation is restricted by
  a character allowlist. These paths show no obvious unrestricted shell
  interpolation, but raw subprocess errors/URLs can expose other task content.
- Read fields depend on backend; AppleScript returns core fields and actual
  Today, but ignores project/area filters and changes deadline filter semantics.
  Reads can silently omit unavailable fields. ID lookups broadly suppress
  script errors. Separator serialization has the same framing risk.
- URL writes support title, notes, schedule, deadline, tags, checklists,
  containers, completion/cancellation, and project operations. Updates use IDs;
  notes/tags replace, `add-tags` merges. None is omitted; empty strings survive.
- Create snapshots IDs and accepts only a unique new same-title item (better
  than matching an old title), but returns `ok: true` even if `match` is null.
  Updates return `ok: true` after dispatch without field verification.
- `open` and AppleScript subprocess calls lack Python timeouts. Some script
  reads have an Apple Event timeout. No write-default gate or recurrence guard.
- Setup requests Full Disk Access for database reads, Automation for the
  AppleScript backend, and a Things URL auth token for existing-item writes.
  None of those database/token requirements is adopted here.

## Supported-interface evidence

Reviewed current official [AI connection guidance](https://culturedcode.com/things/support/articles/5510170/),
[AppleScript commands](https://culturedcode.com/things/support/articles/4562654/),
and [Codex MCP documentation](https://developers.openai.com/codex/mcp).
The latter currently redirects to ChatGPT Learn; `codex mcp add --help` and
`codex mcp remove --help` were also checked locally. No configuration was changed.

Cultured Code documents AppleScript as a supported interface and documents
built-in lists, IDs, task properties, tags, scheduling and completion.
Its `due date` is the deadline. Scheduling is a separate operation. The reviewed
documentation does not establish a recurrence-safety property or verified
start-date read-back/clearing semantics for this implementation.

macOS and scripting tools are present, but no Things app was found by Spotlight
bundle ID or inspection of `/Applications` and the user's `Applications` app
metadata. Therefore the installed dictionary, Things Apple Events, permission
prompts and Cloud sync remain unverified. No live task write or read was run.
The implementation must fail closed on unknown recurrence rather than infer
that a task is nonrepeating. This limits live existing-task mutations in this
tranche; fake-backed service tests can verify the intended mutation contract.
