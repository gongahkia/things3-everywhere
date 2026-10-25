"""Explicit, counts-only stdio verification. No writes or Telegram requests.

--fake selects the test fixture; --live selects the installed production entry
point. Live failures never fall back to synthetic data. Task content stays in
this process's memory and is never printed, logged, or saved.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from things3_everywhere.digest import DEFAULT_TIMEZONE, format_digest
from things3_everywhere.tools import TOOL_DEFINITIONS
from things3_everywhere import validation


ROOT = Path(__file__).resolve().parents[1]
LIMIT = 3
DEPENDENCY_ERRORS = {
    "APP_NOT_FOUND", "MACOS_REQUIRED", "INVALID_CONFIG", "PERMISSION_DENIED",
    "DICTIONARY_UNAVAILABLE", "UNSUPPORTED_INTERFACE", "APP_UNAVAILABLE",
    "SCRIPT_UNAVAILABLE",
}
KNOWN_ERRORS = DEPENDENCY_ERRORS | {"TIMEOUT", "NOT_FOUND", "INVALID_RESPONSE", "SCRIPT_FAILED"}


class CheckFailed(Exception):
    def __init__(self, code="INVALID_RESPONSE"):
        self.code = code


def require(condition):
    if not condition:
        raise CheckFailed()


def check_task(task, *, notes):
    require(type(task) is dict)
    require(set(task) == {"id", "title", "tags", "deadline", "status", "recurrence"}
            | ({"notes"} if notes else set()))
    try:
        validation.task_id(task["id"])
        if task["deadline"] is not None:
            validation.iso_date(task["deadline"])
    except Exception:
        raise CheckFailed() from None
    require(isinstance(task["title"], str))
    require(task["status"] in ("open", "completed", "canceled"))
    require(task["recurrence"] in ("none", "repeating", "unknown"))
    require(type(task["tags"]) is list and all(isinstance(tag, str) for tag in task["tags"]))
    if notes:
        require(isinstance(task["notes"], str))


async def call(session, name, arguments):
    with anyio.fail_after(30):
        result = await session.call_tool(name, arguments)
    body = result.structuredContent
    require(type(body) is dict)
    require(len(result.content) == 1 and result.content[0].type == "text")
    try:
        require(json.loads(result.content[0].text) == body)
    except (ValueError, TypeError):
        raise CheckFailed() from None
    if result.isError:
        error = body.get("error")
        require(type(error) is dict)
        code = error.get("code")
        raise CheckFailed(code if isinstance(code, str) and code in KNOWN_ERRORS else "TOOL_ERROR")
    require("error" not in body)
    return body


async def check_session(session, checks):
    with anyio.fail_after(30):
        initialized = await session.initialize()
        listed = await session.list_tools()
    require(initialized.serverInfo.name == "things3-everywhere")
    require({tool.name for tool in listed.tools} == {tool["name"] for tool in TOOL_DEFINITIONS})
    require(len(listed.tools) == len(TOOL_DEFINITIONS))
    checks["transport"] = {"status": "PASS", "tools": len(listed.tools)}

    pages = {}
    for name in ("things_today", "things_inbox", "things_search"):
        arguments = {"limit": LIMIT, "include_notes": False}
        if name == "things_search":
            arguments["query"] = "THINGS-BRIDGE-SYNTHETIC-NO-MATCH-7f91c2d4"
        page = await call(session, name, arguments)
        require(set(page) == {"tasks", "count", "limit", "has_more"})
        require(type(page["tasks"]) is list and type(page["count"]) is int)
        require(type(page["limit"]) is int and page["limit"] == LIMIT)
        require(page["count"] == len(page["tasks"]) <= LIMIT)
        require(type(page["has_more"]) is bool)
        for task in page["tasks"]:
            check_task(task, notes=False)
        pages[name] = page
        checks[name] = {"status": "PASS", "count": page["count"], "has_more": page["has_more"]}

    candidate = next((task for page in pages.values() for task in page["tasks"]), None)
    if candidate is None:
        checks["things_get_task"] = {"status": "SKIPPED", "reason": "No item in bounded read results."}
    else:
        body = await call(session, "things_get_task", {"id": candidate["id"]})
        require(set(body) == {"task"})
        check_task(body["task"], notes=True)
        require(body["task"]["id"] == candidate["id"])
        checks["things_get_task"] = {"status": "PASS", "count": 1}

    # Format in memory, without displaying task text or invoking a sender.
    digest = format_digest(pages["things_today"], now=datetime.now(timezone.utc))
    require(isinstance(digest, str) and bool(digest))
    checks["digest"] = {"status": "PASS", "timezone": DEFAULT_TIMEZONE, "text_displayed": False}


async def run_check(fake):
    result = {"source": "synthetic" if fake else "live_read_only", "status": "FAIL",
              "writes_enabled": False, "telegram_requests": 0,
              "ui_comparison": "NOT_TESTED", "checks": {}}
    env = {"THINGS_ALLOW_WRITES": "false", "TEST_ENABLE_FAKE_WRITES": "false"}
    if fake:
        command, args = sys.executable, [str(ROOT / "tests/fake_server.py")]
    else:
        command, args = str(ROOT / ".venv/bin/things3-everywhere-mcp"), []
        if os.environ.get("THINGS_APP_PATH"):
            env["THINGS_APP_PATH"] = os.environ["THINGS_APP_PATH"]
    try:
        with anyio.fail_after(150), open(os.devnull, "w") as private_stderr:
            params = StdioServerParameters(command=command, args=args, env=env, cwd=str(ROOT))
            # Never forward subprocess errors that might contain personal data.
            async with stdio_client(params, errlog=private_stderr) as (read, write):
                async with ClientSession(read, write) as session:
                    try:
                        await check_session(session, result["checks"])
                        result["status"] = "PASS"
                    except CheckFailed as error:
                        result["status"] = "BLOCKED" if error.code in DEPENDENCY_ERRORS else "FAIL"
                        result["error_code"] = error.code
                    except TimeoutError:
                        result["error_code"] = "TIMEOUT"
                        result["status"] = "FAIL"
    except Exception:
        # Do not expose exception messages, context, response bodies, or paths.
        result["status"] = "FAIL"
        result["error_code"] = "TRANSPORT_FAILED"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fake", action="store_true", help="Explicit synthetic adapter; no Things access.")
    mode.add_argument("--live", action="store_true", help="Real Things read-only calls; never falls back.")
    args = parser.parse_args()
    result = anyio.run(run_check, args.fake)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
