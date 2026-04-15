from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True, slots=True)
class EntityRecord:
    id: int | str
    name: str
    parent_id: int | str | None
    children_ids: list[int | str]
    component_types: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
