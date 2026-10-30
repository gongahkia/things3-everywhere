from dataclasses import asdict, dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    notes: str
    tags: list[str]
    deadline: str | None
    status: Literal["open", "completed", "canceled"]
    recurrence: Literal["none", "repeating", "unknown"] = "unknown"

    def public(self, *, include_notes=True) -> dict:
        data = asdict(self)
        if not include_notes:
            del data["notes"]
        return data


@dataclass(frozen=True)
class Page:
    tasks: list[Task]
    has_more: bool


class Adapter(Protocol):
    """Internal typed seam. Only ThingsService is an interface-facing API.

    Implementations must guard all mutation methods, reject unsafe recurrence,
    and must never retry a mutation. Read-back belongs to the shared service.
    """

    def list_tasks(self, scope: str, limit: int) -> Page: ...
    def search(self, query: str, limit: int) -> Page: ...
    def get_task(self, id: str) -> Task: ...
    def get_handoff_task(self, id: str) -> Task: ...
    def reveal_task(self, id: str) -> str: ...
    def create_task(self, fields: dict, *, execution: str = "preview") -> str: ...
    def update_task(self, id: str, fields: dict, *, execution: str = "preview") -> str: ...
    def complete_task(self, id: str, *, execution: str = "preview") -> str: ...

