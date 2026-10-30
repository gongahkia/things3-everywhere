# Manual edit handoff — Tranche 07

The bridge prepares a proposal, shows one task when explicitly requested, and
compares its supported fields after the human edits it. Automated update and
completion remain blocked. Recurrence is still unknown in production.

## MCP calls in Codex

Use a fresh Codex session after deploying the reviewed source so that its MCP
server discovers all ten tools. Keep the existing registration's
`THINGS_ALLOW_WRITES=false`. No re-registration or write opt-in is needed.
Use one stable ID returned by a read tool; never substitute a task title.

Ask Codex to make these exact tool calls, replacing the synthetic placeholders:

```text
things_prepare_manual_change({"id":"SELECTED_STABLE_ID","operation":"rename","value":"Synthetic replacement title"})
things_reveal_manual_change({"session_id":"RETURNED_SESSION_ID"})
things_verify_manual_change({"session_id":"RETURNED_SESSION_ID"})
```

Run prepare first. Review its proposal and explicitly approve opening that task
before calling reveal. Make the edit yourself in Things, then tell Codex to call
verify. Searching, reading, and preparing never reveal an item. A reveal receipt
is not evidence of an edit. Do not repeat reveal automatically after an error.
Tool descriptions express this user-approval boundary; the server cannot prove
that a conversational approval occurred.

Supported proposals:

| Operation | Replacement value |
| --- | --- |
| `rename` | Nonblank title, maximum 500 characters. |
| `replace_notes` | Notes, maximum 20,000 characters; empty text clears. |
| `change_deadline` | Valid `YYYY-MM-DD`; deadline clearing is not supported. |
| `complete` | Omit `value`. Expected status is completed. |

These calls must share one running MCP server process. Separate CLI invocations
create separate services and cannot share a handoff. Session IDs are versioned,
private handles, not Things IDs; they must not be committed or logged publicly.
The trusted local MCP client can use its own handles; this is not a multi-user
service or a public endpoint.

## Lifetime, comparison, and limitations

A process holds at most 32 sessions. Each expires 15 minutes after preparation;
expired records are removed on the next handoff call, and all records disappear
on process exit. No snapshot, notes, title, or session token is persisted.
Capacity exhaustion returns an explicit error instead of evicting an active
snapshot. Verification consumes the session even when its read fails. Reveal
allows one attempt. Preparation of a new session captures a new baseline; it
cannot recover the baseline of an expired or lost session.

The private snapshot includes title, notes, tags, deadline, and status. These are
the supported fields compared; notes are needed to detect unintended changes,
but unrelated note contents are never returned by handoff comparison. The preview
returns the proposed value only. Verification returns changed field names and
whether the intended change was observed. Tag ordering is not significant.
This does not verify checklists, placement, start dates, recurrence, or Cloud sync.

| Outcome | Meaning |
| --- | --- |
| `prepared` | Proposal and baseline captured; no UI change. |
| `revealed` | Show command returned; human edit still required. |
| `verified` | Expected field changed and all other compared fields match. |
| `mismatched` | Expected value is missing or other compared fields changed. |
| `unavailable` | Task could not be safely read or revealed, including missing ID, unknown item kind, timeout, or permission failure. |
| `inconclusive` | Session missing/expired/consumed, state changed before reveal, repeated reveal attempt, or proposed value already matched the baseline. |

Verification reports observed state, not who caused it. Changes made and reverted
between snapshots cannot be detected. Concurrent Things/Cloud changes can occur
between checks; no atomic transaction or compare-and-set is claimed. If completion
moves the task into Logbook and lookup by the same ID fails, the result is
unavailable, never successful completion.

## Supported reveal mechanism

The fixed AppleScript resolves `to do id targetID`, checks its ID, requires exactly
one match in the documented `to dos` collection, and checks its class before any
`show` command or activation. The Things 3.24.1 dictionary defines `to do` (`tstk`)
and its subclass `selected to do` (`tslt`) as task classes; both are accepted only
with that collection membership. Projects inherit from `to do`, but are exposed
through the separate `projects` collection. A live read-only probe found that
`to do id` can wrap a project as `selected to do`, so class alone is insufficient.
The collection check rejected that project and accepted the disposable Inbox
task, whose runtime class was also `selected to do` despite not being selected.
Unknown or unavailable classes and nonunique collection matches fail closed.
This establishes item kind only: it does not distinguish a repeating copy or
template. The supported collections are described in the
[official commands guide](https://culturedcode.com/things/support/articles/4562654/).

Preparation and verification use the same guarded read. All values travel as
JSON over stdin, with no script interpolation, arbitrary execution, database
access, or private experimental property access. The inspected Things 3.24.1
dictionary and [official AppleScript commands](https://culturedcode.com/things/support/articles/4562654/)
support these mechanisms. Compilation is checked separately from live reveal; the Tranche 07 rename
handoff was subsequently live-verified. Expanded tests remain pending below.

## Controlled live test — approval required

1. Supply a separate disposable task you are willing to edit manually. The
   Tranche 06 task stays untouched unless separately authorized.
2. Read its stable ID privately and propose one synthetic title replacement.
3. Explicitly approve the target and manual test before preparation/reveal.
4. Prepare and reveal within the same MCP process. Inspect the selected task.
5. Manually rename it in Things. Verify by the same ID within 15 minutes.
6. Optionally confirm the change on iPhone yourself; record only the outcome.
7. Completion is a separate explicitly approved manual test. Do not automatically
   complete, undo, or delete the task afterward.

Run synthetic checks before this test:

```sh
THINGS_ALLOW_WRITES=false .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src/things3_everywhere tests scripts
.venv/bin/python scripts/check_docs.py
.venv/bin/python scripts/check_mcp.py --fake
THINGS_ALLOW_WRITES=false .venv/bin/python scripts/check_mcp.py --live
git diff --check
```

The live MCP checker calls only existing read tools. It does not prepare sessions,
reveal items, or edit tasks. Synthetic protocol tests exercise the new handoff
through production MCP with a fake adapter.

## Future automatic editing: evidence required

Current supported interfaces do not document a reliable ordinary/copy/template
classifier. This is a current capability limitation, not a claim that automatic
editing can never be supported.

- **Platform contract:** a documented recurrence signal or an enforceable
  conditional mutation rejecting every excluded target could justify a future
  implementation after verification of its exact scope. None was established
  in Tranche 06. Item class and stable ID alone are insufficient.
- **User confirmation:** authorizes a chosen action but does not supply machine-
  verifiable recurrence metadata. It cannot enable the existing blocked paths.
- **Heuristics:** titles, creation history, tags, ID allowlists, and absence from
  a visible list are not accepted evidence of recurrence safety.
- **Private APIs:** the hidden experimental JSON property, Things database,
  and Things Cloud credentials are outside this project's supported integration.

[Shortcuts actions](https://culturedcode.com/things/support/articles/9596775/)
provide editing but no documented recurrence property. The
[URL scheme](https://culturedcode.com/things/support/articles/2803573/)
restricts some fields on repeating items, without establishing the general
classification contract needed by this bridge. Switching interfaces alone does
not meet the policy.

The next automatic-editing investigation should obtain an authoritative contract
covering ordinary tasks, templates, copies, repeating-project children, and changes
between inspection and mutation. Do not introduce an override while that evidence
is absent. If such a contract becomes available, start with one replacement field
and a separately approved disposable target. Add single-dispatch tests, changed-
state checks, partial-failure handling, restart/replay protection, and private
operation receipts before any controlled automatic test. Local deduplication
cannot guarantee exactly-once execution in Things; uncertain outcomes still need
inspection and no automatic replay.

## Tranche 08 lifecycle and verification hardening

Baseline: branch `main`, HEAD `9bf43afd5055d68b58c5707e35472c34ba15e8f5`,
97 passing tests. The ten modified and three untracked Tranche 07 files were
preserved. The expanded suite has 107 tests, all passing on the verification Mac.

Handles now use `h1.<random service-instance namespace>.<random secret>`.
Each service instance generates a 128-bit namespace and each preparation a
192-bit secret. No task data is encoded in the handle. The namespace is not an
authentication claim: a caller can fabricate a different namespace. A mismatch
proves only that the supplied namespace differs, not that a restart occurred.
The stdio entry point creates one service per server process and retains it for
that connection. Replacing the process or service loses every snapshot.

The lifetime remains 900 monotonic seconds after snapshot capture, with at most
32 active snapshots. Capacity exhaustion rejects preparation without eviction.
Up to 128 tombstones retain only a SHA-256 handle digest, reason and monotonic
expiry, for at most 900 seconds after retirement. They contain no task identity,
proposal or snapshot. Oldest tombstones can be evicted; diagnostic precision is
then deliberately lost. Expiration cleanup runs on handoff calls; there is no
background service or disk persistence. Idle expired snapshots are inaccessible
but remain in memory until cleanup or process exit.

| Reason | What is known |
| --- | --- |
| `SESSION_EXPIRED` | This instance observed expiration, including expiry during a successful read. |
| `SESSION_CONSUMED` | Verification already consumed the session, including a failed read. |
| `SESSION_INSTANCE_MISMATCH` | Handle namespace differs; restart, replacement, different routing or fabricated input cannot be distinguished. |
| `SESSION_HANDLE_INVALID` | Unsupported handle format, including legacy handles. MCP schema errors may instead return sanitized `INVALID_INPUT`. |
| `SESSION_UNKNOWN` | Well-formed local-namespace handle has no record; unknown input, lost state and an evicted/aged-out tombstone are indistinguishable. |
| `STATE_CHANGED_BEFORE_REVEAL` | Compared state changed before reveal; snapshot invalidated. |
| `REVEAL_ALREADY_ATTEMPTED` | One reveal was already attempted; never automatically retry. |

Every unavailable-session outcome is inconclusive. Stop, explain the reason,
prepare a new baseline only with user authorization, and obtain new explicit
reveal approval. Never silently replace a snapshot or carry approval across
sessions. A successful reveal does not prove an edit.

Two preparations for one task have independent snapshots and can observe the
same later change; this is not causal attribution. Handoff operations retain the
existing service-local lock, so simultaneous verification of one handle has one
consumer. Ordinary read-only MCP operations do not acquire that lock. No new
global lock was added. Stale reveal invalidates the session; read failures on
reveal use up its one reveal attempt but leave verification available. Verification
consumes before reading, even if the task disappears or the read is malformed.
A read failure reports unavailable; successful reads finishing after expiry
report inconclusive. No comparison is atomic with other Things/Cloud changes.

Snapshots are validated using the adapter's existing record validator. Title,
notes, deadline and status compare exactly; tags compare as unordered sets both
before reveal and during verification. Unexpected status or additional field
changes produce `mismatched`. Only **no unexpected changes among compared
fields** can be asserted, never that no other task properties changed.

Notes are complete replacements, including exact Unicode and line breaks.
Empty text means clear; unchanged notes give `ALREADY_MATCHED_BEFORE` when no
other compared field changed. No append or newline normalization is performed.
Deadlines use local calendar `YYYY-MM-DD` values, independent of clock time;
absence is distinct from a populated date. Addition and replacement are supported;
clearing remains unsupported. Start dates and reminders are not substitutes.

Completion proposes `status=completed`. Read-back of the same stable ID must
succeed and show the expected status; disappearance is unavailable, never proof
of completion. The [Things commands guide](https://culturedcode.com/things/support/articles/4562654/)
documents the Logbook and configurable logging behavior, including manual logging.
Completed status therefore does not establish placement. During the approved
completion test, separately check only the selected ID's membership in
`to dos of list "Logbook"` using an ID-filtered count. Do not list completed
history, invoke `log completed now`, or alter logging preferences. If the guarded
lookup cannot retrieve the completed task, stop and investigate before adding a
fallback. No Logbook retrieval endpoint or extra compared field is added here.

### Lifecycle evidence and live status

The global registration points directly to the local virtualenv stdio executable
with `THINGS_ALLOW_WRITES=false`. Source inspection and synthetic stdio tests
confirm service reuse on one connection and loss across process replacement.
Multiple bridge processes were observed under the same parent; that observation
does not establish which process served a historical request. The earlier
`SESSION_UNAVAILABLE` has no retained cause evidence. **Its root cause is unknown.**
The [Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp)
describes stdio launch configuration but does not establish a guarantee that
successive conversational calls survive reconnects in the same process.
Do not assume process affinity across turns or reconnects.

Python source changes require reconnecting the intended MCP server to load them;
editing files does not replace already-imported code. Do not change the persistent
registration, kill unrelated bridge processes, or reconnect during an active
handoff. New `h1` handles identify the updated implementation. A new connection
must prepare its own session and obtain approval.

Tranche 07 rename was live-verified on Things 3.24.1: only title changed among
the five compared fields. Tranche 08 notes, deadline and completion/Logbook tests
are **pending user approval and manual action**, not live-verified. Run them one
at a time in that order. Select a disposable target explicitly; approve a literal
notes replacement and a specific deadline before each test. Completion is last.
The original Tranche 06 task is excluded. Keep task IDs, titles, notes and session
handles out of repository reports and logs. Recurrence remains unknown; automatic
update and completion remain blocked even if a user asserts nonrecurrence.

Tranche 08 validation: 107 full-suite tests and 25 focused handoff tests passed;
Python and AppleScript compilation, documentation checks, synthetic MCP checks,
production read-only MCP smoke checks and diff whitespace checks passed. The
registered long-running connection still returned the legacy `SESSION_UNAVAILABLE`
for a synthetic invalid handle, while fresh processes exercised the new diagnostics.
Reconnect the intended client/server before preparing the first Tranche 08 live
session. No Tranche 08 reveal or manual edit has been performed yet.
