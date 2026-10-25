from dataclasses import dataclass
from collections.abc import Mapping

from .errors import BridgeError
from .model import Task
from . import validation as v


@dataclass(frozen=True)
class WritePolicy:
    enabled: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str]):
        # Fail closed: TRUE, yes, 1 and whitespace are not opt-ins.
        return cls(enabled=env.get("THINGS_ALLOW_WRITES") == "true")

    def require(self, execution: str):
        v.execution(execution)
        if execution != "execute":
            raise BridgeError("EXECUTION_REQUIRED", "A mutation requires execution='execute'.")
        if self.enabled is not True:
            raise BridgeError("READ_ONLY", "Live writes are disabled. Set THINGS_ALLOW_WRITES=true "
                              "only for an explicitly authorized write session.")


def require_nonrepeating(task: Task):
    if task.recurrence != "none":
        raise BridgeError("RECURRENCE_UNSAFE", "The supported interface cannot establish a safe "
                          "nonrepeating target. Existing-task execution is blocked.")

