import argparse
import json
import os
import sys

from .errors import BridgeError, unexpected_error
from .runtime import live_service
from .safety import WritePolicy
from .tools import METHODS, dispatch
from .transport import dictionary_summary, find_app
from .briefing import briefing


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes rejected values, which might include a misplaced secret.
        self.print_usage(sys.stderr)
        self.exit(2, "Invalid command line; use --help. Argument values are not logged.\n")


def doctor():
    result = {"writes_enabled": WritePolicy.from_env(os.environ).enabled,
              "mechanism": "AppleScript", "cloud_sync": "unverified",
              "existing_task_execution": "blocked_recurrence_unknown"}
    try:
        app = find_app(os.environ.get("THINGS_APP_PATH"))
        result["app_found"] = True
        result["dictionary"] = dictionary_summary(app)
        result["automation_permission"] = "not_tested"
        return result, not result["dictionary"]["required_terms_present"]
    except BridgeError as error:
        result["error"] = error.public()
        return result, True


def summarize(result):
    if "error" in result:
        return result
    if "tasks" in result:
        return {key: result[key] for key in ("count", "limit", "has_more")}
    if "task" in result:
        return {"count": 1, "outcome": result.get("outcome", "read")}
    return {key: value for key, value in result.items() if key not in {"id", "fields"}}


def main():
    parser = PrivateArgumentParser(description="Local Things bridge; call arguments are JSON on stdin.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor", help="Check app and scripting dictionary without reading tasks.")
    call = subcommands.add_parser("call", help="Call one tool with a JSON object on stdin (default {}).")
    call.add_argument("tool", choices=METHODS)
    call.add_argument("--summary", action="store_true", help="Print counts/outcomes without task content or IDs.")
    digest = subcommands.add_parser("digest", help="Preview Today locally or explicitly send once to Telegram.")
    digest_commands = digest.add_subparsers(dest="digest_action", required=True)
    for action in ("preview", "send-once"):
        command = digest_commands.add_parser(action)
        command.add_argument("--fake", action="store_true", help="Use synthetic demo data, without reading Things.")
        command.add_argument("--timezone", help="IANA briefing timezone; default Asia/Singapore.")
        if action == "send-once":
            command.add_argument("--execute", action="store_true", help="Actually send; otherwise dry-run only.")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            result, failed = doctor()
        elif args.command == "digest":
            result = briefing(action=args.digest_action, fake=args.fake, zone=args.timezone,
                              execute=getattr(args, "execute", False))
            failed = result["outcome"] in ("partial", "unknown", "rejected")
        else:
            raw = "" if sys.stdin.isatty() else sys.stdin.read(100_001)
            if len(raw) > 100_000:
                raise BridgeError("INVALID_INPUT", "CLI JSON input exceeds 100000 characters.")
            try:
                arguments = json.loads(raw) if raw.strip() else {}
            except ValueError:
                raise BridgeError("INVALID_INPUT", "Provide one valid JSON object on stdin.") from None
            result, failed = dispatch(live_service(), args.tool, arguments)
            if args.summary:
                result = summarize(result)
    except BridgeError as error:
        result, failed = {"error": error.public()}, True
    except Exception:
        result, failed = {"error": unexpected_error().public()}, True
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return_code = 1 if failed else 0
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
