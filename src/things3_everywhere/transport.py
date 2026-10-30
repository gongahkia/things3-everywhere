"""Fixed AppleScript executable, JSON over stdin, no shell or content in argv."""

from pathlib import Path
import json
import os
import plistlib
import subprocess
import sys
import xml.etree.ElementTree as ET

from .errors import BridgeError
from .safety import WritePolicy
from . import validation as v

BUNDLE_ID = "com.culturedcode.ThingsMac"
SCRIPT = Path(__file__).with_name("things.applescript")


def find_app(configured: str | None = None) -> Path:
    if sys.platform != "darwin":
        raise BridgeError("MACOS_REQUIRED", "This adapter requires macOS with Things 3 installed.")
    if configured and (not Path(configured).is_absolute() or not configured.endswith(".app")):
        raise BridgeError("INVALID_CONFIG", "THINGS_APP_PATH must be an absolute .app path.")
    candidates = [Path(configured)] if configured else [
        base / name for base in (Path("/Applications"), Path.home() / "Applications")
        for name in ("Things3.app", "Things.app")]
    for app in candidates:
        try:
            with (app / "Contents/Info.plist").open("rb") as stream:
                metadata = plistlib.load(stream)
            if metadata.get("CFBundleIdentifier") == BUNDLE_ID:
                return app
        except (OSError, plistlib.InvalidFileException):
            continue
    raise BridgeError("APP_NOT_FOUND", "Things 3 was not found. Install/open Things, or set "
                      "THINGS_APP_PATH to its app bundle. No database fallback is available.")


def dictionary_summary(app: Path, *, run=subprocess.run) -> dict:
    try:
        result = run(["/usr/bin/sdef", str(app)], capture_output=True, timeout=10, check=False)
    except subprocess.TimeoutExpired:
        raise BridgeError("TIMEOUT", "Reading the Things scripting dictionary timed out.") from None
    except OSError:
        raise BridgeError("DICTIONARY_UNAVAILABLE", "The macOS sdef tool is unavailable.") from None
    if result.returncode:
        raise BridgeError("DICTIONARY_UNAVAILABLE", "The Things scripting dictionary could not be read.")
    try:
        root = ET.fromstring(result.stdout)
    except ET.ParseError:
        raise BridgeError("DICTIONARY_UNAVAILABLE", "Things returned an invalid scripting dictionary.") from None
    properties = {p.get("name") for p in root.iter("property")}
    classes = {p.get("name") for p in root.iter("class")}
    required = {"id", "name", "notes", "tag names", "due date", "status"}
    compatible = required <= properties and {"to do", "list", "tag"} <= classes
    return {"required_terms_present": compatible,
            "start_date_supported": False, "recurrence_detection_supported": False}


class AppleScriptTransport:
    def __init__(self, policy=WritePolicy(), *, app_path=None, run=subprocess.run,
                 preflight=None, timeout=20):
        self.policy = policy
        self.app_path = app_path
        self.run = run
        self.preflight = preflight or self._preflight
        self.timeout = timeout

    def _preflight(self):
        app = find_app(self.app_path)
        if not dictionary_summary(app, run=self.run)["required_terms_present"]:
            raise BridgeError("UNSUPPORTED_INTERFACE", "The installed Things dictionary lacks required terms.")

    def call(self, operation, payload):
        if operation not in {"today", "inbox", "search", "get", "create", "inspect_task", "show_task"}:
            raise BridgeError("UNSUPPORTED_OPERATION", "This transport operation is not available.")
        writing = operation == "create"
        if writing:
            self.policy.require(payload.get("execution", "preview"))
            payload = {"fields": v.fields(payload.get("fields"), create=True), "execution": "execute"}
        elif operation in {"get", "inspect_task", "show_task"}:
            payload = {"id": v.task_id(payload.get("id"))}
        elif operation == "search":
            payload = {"query": v.text(payload.get("query"), "query", 500, nonempty=True),
                       "limit": v.limit(payload.get("limit", 50))}
        else:
            payload = {"limit": v.limit(payload.get("limit", 50))}
        self.preflight()
        request = json.dumps({**payload, "operation": operation}, ensure_ascii=True).encode("utf-8")
        env = dict(os.environ)
        env["THINGS_ALLOW_WRITES"] = "true" if self.policy.enabled else "false"
        try:
            result = self.run(["/usr/bin/osascript", str(SCRIPT)], input=request,
                              capture_output=True, timeout=self.timeout, check=False, env=env)
        except subprocess.TimeoutExpired:
            raise BridgeError("TIMEOUT", "Things did not respond within the subprocess timeout. "
                              "Inspect Things before retrying a write.",
                              outcome="unknown" if writing else "not_attempted") from None
        except OSError:
            raise BridgeError("SCRIPT_UNAVAILABLE", "The macOS scripting process could not be started.") from None
        if result.returncode:
            # Compilation and process errors may contain private content; never echo stderr.
            code = "PERMISSION_DENIED" if b"(-1743)" in result.stderr else "SCRIPT_FAILED"
            raise BridgeError(code, "AppleScript failed. Check Things installation and Automation permission "
                              "for the launching app; inspect Things before retrying a write.",
                              outcome="unknown" if writing else "not_attempted")
        try:
            if len(result.stdout) > 4_000_000:
                raise ValueError()
            response = json.loads(result.stdout)
            if type(response) is not dict or type(response.get("ok")) is not bool:
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            raise BridgeError("INVALID_RESPONSE", "AppleScript returned an invalid or oversized response.",
                              outcome="unknown" if writing else "not_attempted") from None
        if not response["ok"]:
            errors = {
                -1743: ("PERMISSION_DENIED", "Allow the launching app to control Things in System Settings → "
                        "Privacy & Security → Automation. Full Disk Access is not needed."),
                -1712: ("TIMEOUT", "The Things Apple Event timed out. Inspect Things before retrying a write."),
                -1728: ("NOT_FOUND", "No task exists with that stable ID."),
                -600: ("APP_UNAVAILABLE", "Things is unavailable. Open Things and retry the read."),
                7104: ("ITEM_KIND_UNSUPPORTED", "Target is not a verified to-do item."),
                7105: ("INVALID_RESPONSE", "Things returned a different task ID."),
                7101: ("READ_ONLY", "The script's write gate rejected execution."),
                7102: ("UNKNOWN_TAG", "Every supplied tag must already exist with a unique matching name."),
            }
            code, message = errors.get(response.get("error_number"),
                                       ("SCRIPT_FAILED", "Things rejected the operation; no automatic retry was made."))
            # A lost response or event timeout cannot prove that the app did not mutate.
            uncertain = writing and (response.get("write_started") is not False or response.get("error_number") == -1712)
            raise BridgeError(code, message, outcome="unknown" if uncertain else "not_attempted")
        return response

