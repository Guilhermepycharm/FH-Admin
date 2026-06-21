from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from rapidfuzz import fuzz
except ModuleNotFoundError:  # pragma: no cover - optional at edit time
    fuzz = None


def normalize_name(value: str) -> str:
    lowered = value.casefold()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


@dataclass(frozen=True)
class Entry:
    entry_id: int
    name: str
    description: str


class Catalog:
    def __init__(
        self,
        items: dict[int, Entry],
        weapons: dict[int, Entry],
        armors: dict[int, Entry],
        skills: dict[int, Entry],
        actors: dict[int, Entry],
        states: dict[int, Entry],
    ) -> None:
        self.items = items
        self.weapons = weapons
        self.armors = armors
        self.skills = skills
        self.actors = actors
        self.states = states

    @classmethod
    def load(cls, data_dir: Path) -> "Catalog":
        return cls(
            items=_load_database(data_dir / "Items.json", "description"),
            weapons=_load_database(data_dir / "Weapons.json", "description"),
            armors=_load_database(data_dir / "Armors.json", "description"),
            skills=_load_database(data_dir / "Skills.json", "description"),
            actors=_load_database(data_dir / "Actors.json", "profile"),
            states=_load_database(data_dir / "States.json", "message1"),
        )

    def entries_for_kind(self, kind: str) -> dict[int, Entry]:
        mapping = {
            "items": self.items,
            "weapons": self.weapons,
            "armors": self.armors,
            "skills": self.skills,
            "actors": self.actors,
            "states": self.states,
        }
        return mapping[kind]

    def search(self, kind: str, query: str, limit: int = 20) -> list[Entry]:
        entries = self.entries_for_kind(kind)
        if query.strip().isdigit():
            entry = entries.get(int(query.strip()))
            return [entry] if entry is not None else []

        normalized = normalize_name(query)
        if not normalized:
            return list(entries.values())[:limit]

        if fuzz is not None:
            scored: list[tuple[int, Entry]] = []
            for entry in entries.values():
                hay_name = normalize_name(entry.name)
                hay_full = normalize_name(f"{entry.entry_id} {entry.name} {entry.description}")
                score = max(
                    fuzz.partial_ratio(normalized, hay_name),
                    fuzz.partial_ratio(normalized, hay_full),
                )
                if score >= 45:
                    scored.append((score, entry))
            scored.sort(key=lambda item: (-item[0], item[1].entry_id))
            return [entry for _, entry in scored[:limit]]

        exact: list[Entry] = []
        prefix: list[Entry] = []
        contains: list[Entry] = []
        for entry in entries.values():
            haystack = normalize_name(f"{entry.entry_id} {entry.name} {entry.description}")
            if normalized == normalize_name(entry.name):
                exact.append(entry)
            elif haystack.startswith(normalized):
                prefix.append(entry)
            elif normalized in haystack:
                contains.append(entry)
        return (exact + prefix + contains)[:limit]


def _load_database(path: Path, description_key: str) -> dict[int, Entry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    result: dict[int, Entry] = {}
    for index, entry in enumerate(raw):
        if not entry:
            continue
        name = str(entry.get("name") or f"ID {index}")
        description = str(entry.get(description_key) or "")
        result[index] = Entry(index, name, description)
    return result
