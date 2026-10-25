# Tranche 04 — offline runtime verification

Date: **2026-10-25**. Repository identity confirmed:
`gongahkia/things3-everywhere`, HTTPS origin. Baseline commit:
`723ade4bc70c8515ef808ae17a580e21d62e922c`. The working tree was clean at the start;
no applicable repository instructions were found. During verification, HEAD
advanced outside the agent's actions to
`9abf965c489ee32b07cb079ca89b863e8bed02ed` (`thanks`), containing the seven
code/test/documentation changes listed below. Their working files match that
commit. This report remains untracked at handoff. The agent did not stage,
commit, push, transfer files, switch branches, or change remotes, accounts, or
global configuration. Remote availability of the new commit was not checked.

## Classification and evidence

**APP_NOT_FOUND is an expected environmental limitation.** The user confirms
Things is intentionally absent on this development Mac. No app-location search,
launch, installation, scripting-dictionary extraction from an installed app, or
Automation permission prompt was attempted during this tranche.

Source review confirms that the adapter checks readable bundle metadata at an
explicit configured path or standard system/user application paths. It checks
the bundle identity before dictionary inspection or AppleScript execution; it
does not depend on Spotlight or whether the app is running. Missing, unreadable,
or malformed metadata can all lead to APP_NOT_FOUND, so the code alone is not
proof of universal absence. Here, the user's confirmation resolves the
environmental classification. There is no evidence requiring a detection repair.
Discovery, adapter behavior, write policy, and production tool definitions were
left unchanged.

The production-backend dependency tests point `THINGS_APP_PATH` at a deliberately
absent path inside a temporary test directory. Today, Inbox, search, and get-by-ID
return structured APP_NOT_FOUND errors with an actionable configuration hint,
without task data or a crash. The same process remains responsive to tool
discovery. These are **offline missing-dependency tests**, not successful live
Things integration tests and not a search for an installed app.

## Files changed

| File | Why |
| --- | --- |
| [tests/fake_server.py](../tests/fake_server.py) | Use production main/logging/SDK/stdio with fake service composition. Add an explicit synthetic banner and fail-on-write adapter whose mutation-entry counter fails the child process if any forbidden call occurs. |
| [tests/test_protocol.py](../tests/test_protocol.py) | Retain actual tool-call coverage against the stronger fixture; add all four read-tool dependency errors and process-liveness checks through the real backend with an absent fixture path. |
| [scripts/check_mcp.py](../scripts/check_mcp.py) | User-invoked, counts-only verification client for the target Mac. Requires explicit --fake or --live; checks schemas, bounds reads, formats locally in memory, and never substitutes fake data for live failures. |
| [tests/test_mcp_check.py](../tests/test_mcp_check.py) | Verify synthetic transport, empty results, explicit modes, malformed success/error sanitization, and blocked live-backend diagnostics without fallback. |
| [docs/mac-setup.md](mac-setup.md) | Extend the existing guide with runtime outcome classification and a portable target-Mac runbook; fix a stale README link. |
| [docs/verification.md](verification.md) | Record separate offline/live statuses, actual MCP call coverage, and the fail-on-write proof. |
| [docs/tranche-03-report.md](tranche-03-report.md) | Remove one stale link to the subsequently removed README, preserving the historical record. |
| This report | Record the evidence, checks, limits, and next commands. |

The existing production adapter remains the sole task implementation. The
diagnostic is a local MCP client using the installed SDK, not a new MCP server or
remote-access feature. Its live mode calls only read tools. It suppresses private
results and child errors, emits counts/schema outcomes, and stops its child
process when complete. There is no persistent process or listener.

## Tests executed

Runtime: repository environment **Python 3.11.16**, **uv 0.12.6**; installed
dependencies were compatible (`uv pip check`, 30 packages). No dependency or
lockfile changes were required. Entry points were checked from `pyproject.toml`
and CLI help rather than inferred from the shell's Python version.

| Check | Result |
| --- | --- |
| Baseline `uv run --frozen python -m unittest discover -s tests -v` | **72 passed**; no pre-existing unit-test failures. |
| Baseline documentation check | **Failed** on two stale README links, now repaired without recreating the removed README. |
| Focused `test_protocol.py` suite | **5 passed**. |
| Focused `test_mcp_check.py` suite | **6 passed**. |
| Final `uv run --frozen python -m unittest discover -s tests -v` | **79 passed**. |
| `uv run --frozen python -m compileall -q src/things3_everywhere tests scripts` | Passed. |
| `uv run --frozen python scripts/check_mcp.py --fake` | PASS: seven tools; synthetic Today count 2, Inbox/search count 0, get-by-ID count 1; local digest formatting passed. |
| Synthetic digest preview and send-once dry run | Both passed and reported **0 Telegram requests**. |
| `uv run --frozen python scripts/check_docs.py` | Passed across **12 Markdown files** after link repairs. |
| `git diff --check` and content review | Passed; reviewed changes contain synthetic data and no discovered credentials/personal task content. The pattern check is not an exhaustive secret scan. |

Transport coverage includes initialization, discovery, actual tool invocation,
structured/text response agreement, missing IDs, validation failures, unknown
tools, previews, and rejection of all three mutation contracts in read-only
mode. Rejected writes must never enter the fail-on-write fake's mutation methods;
the process exit assertion detects attempted calls even if an internal exception
was caught. Separate fake-only opt-in tests exercise existing mutation contracts;
no live adapter mutation was used as a safety probe.

The full suite also checks digest timezones, date/recurrence handling, Unicode,
dry-run isolation, and Telegram responses through mocked HTTP. Existing pure
AppleScript helper tests contain no Things application clause. No Telegram API
request or message was made, even if credentials existed in the environment.

## Status and remaining checks

| Area | Status |
| --- | --- |
| Offline validation | **PASS**. |
| Live read-only MCP / Things integration | **BLOCKED — NOT TESTED**, app intentionally absent on development Mac. |
| Live task writes | **NOT TESTED**. |
| Telegram delivery | **NOT TESTED**. |
| iPhone workflow | **MANUAL VERIFICATION PENDING**. |

Actual Things reads, installed dictionary compatibility, Automation consent,
comparison with the Things UI, locale behavior, and target-Mac timezone effects
remain unverified. No personal task IDs, titles, notes, inventories, or migration
data were read. Things Cloud/iPhone sync has not been inferred from offline tests.
Existing recurrence restrictions and unsupported date writes remain in force.

## Next user-run verification

Use the [portable runbook](mac-setup.md#portable-verification-on-a-mac-with-things-installed)
on a Mac where Things is already installed. First ensure that the reviewed
implementation and the newly added script actually exist in that checkout.
The baseline hash does not include this tranche's implementation. The code and
tests are now recorded locally in `9abf965c489ee32b07cb079ca89b863e8bed02ed`;
ensure that revision or a reviewed descendant is present on the target Mac.
Do not assume its availability on GitHub or the other machine. The agent did
not upload or transfer it, and this report is not part of that commit.

From inside that intended checkout:

```sh
repo_root="$(git rev-parse --show-toplevel)" || exit 1
cd "$repo_root"
git remote -v
git rev-parse HEAD
git status --short
test -f scripts/check_mcp.py
uv sync --frozen
uv run --frozen python scripts/check_mcp.py --fake
```

After reviewing the installed dictionary and the runbook's permission step,
run these **on the target Mac only**:

```sh
THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere doctor &&
THINGS_ALLOW_WRITES=false .venv/bin/python scripts/check_mcp.py --live
```

No task data, credentials, accounts, or persistent configuration were changed.
No live writes were enabled, no Telegram requests/messages were sent, and no
scheduler, background service, public listener, tunnel, or remote access was
installed. Only temporary test/diagnostic subprocesses ran. Controlled writes
remain a separate user-invoked procedure and were not executed.
