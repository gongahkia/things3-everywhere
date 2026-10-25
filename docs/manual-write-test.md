# Optional manual test — user-run only

No command in this procedure was used to write to Things during tranche 01.
The smallest test is **one creation**, explicitly chosen by you, with no tags,
dates or follow-on edits. This checks fewer unverified behaviors at once.

1. Install/open Things on this Mac. Inspect its scripting dictionary. Run
   `uv sync --frozen` and the read-only diagnostic and list check from
   [Mac setup](mac-setup.md).
   Resolve any missing-app or Automation error first. Keep the MCP registration
   read-only.
2. Choose and explicitly identify a unique disposable task title, for example
   `DISPOSABLE THINGS BRIDGE TEST — <your chosen unique suffix>`. It must be an
   ordinary task that you are willing to create in Inbox. Do not choose a real
   work task or a recurring template. This instruction does not authorize an
   agent to choose a real task on your behalf.
3. Substitute that exact title below, retaining valid JSON. Preview first:

   ```sh
   THINGS_ALLOW_WRITES=false .venv/bin/things3-everywhere call things_create_task <<'JSON'
   {"fields":{"title":"<YOUR EXPLICITLY CHOSEN DISPOSABLE TITLE>"},"execution":"preview"}
   JSON
   ```

   Expect `outcome: preview` and `mutated: false`. Verify no new task exists.
4. Only after reviewing that exact request, run **once** with the same title:

   ```sh
   THINGS_ALLOW_WRITES=true .venv/bin/things3-everywhere call things_create_task <<'JSON'
   {"fields":{"title":"<YOUR EXPLICITLY CHOSEN DISPOSABLE TITLE>"},"execution":"execute"}
   JSON
   ```

   The environment assignment applies to this process only. Expect either a
   verified result with the created stable ID, or an explicit error. Never repeat
   the command automatically if it fails, times out, or cannot verify its result.
   Inspect Inbox first; a task may already have been created.
5. Inspect the task in Things and optionally use `things_get_task` with the
   returned ID. Confirm the title, empty notes/tags, absent deadline and open
   status. Do not record a personal inventory in the repository. Clean up the
   disposable task manually in Things if desired; there is no delete tool.

Live update and completion are deliberately blocked for every existing task,
including this newly created one, because the current supported adapter cannot
prove recurrence safety. A user assertion or an ID cache does not bypass that
restriction. Exercise those contracts with the fake tests; a later tranche must
verify a supported recurrence signal before enabling their live paths.

Creating with notes, tags or deadlines needs separate explicit tests after this
minimal test passes. Start dates and deadline clearing remain unsupported.
This procedure verifies only the local state; do not infer Things Cloud sync.
