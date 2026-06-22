from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OwnedEntry:
    entry_id: int
    quantity: int


def inventory_key(kind: str) -> str:
    return {
        "items": "_items",
        "weapons": "_weapons",
        "armors": "_armors",
    }[kind]


def inventory_map(data: dict, kind: str) -> dict:
    inventory = data["party"][inventory_key(kind)]
    if not isinstance(inventory, dict):
        raise TypeError(f"party.{inventory_key(kind)} is not a dict")
    return inventory


def list_owned_entries(data: dict, kind: str) -> list[OwnedEntry]:
    inventory = inventory_map(data, kind)
    result: list[OwnedEntry] = []
    for key, value in inventory.items():
        if key.isdigit() and isinstance(value, int) and value > 0:
            result.append(OwnedEntry(int(key), value))
    result.sort(key=lambda entry: entry.entry_id)
    return result


def set_quantity(data: dict, kind: str, entry_id: int, quantity: int) -> None:
    inventory = inventory_map(data, kind)
    key = str(entry_id)
    if quantity <= 0:
        inventory.pop(key, None)
    else:
        inventory[key] = quantity


def add_quantity(data: dict, kind: str, entry_id: int, delta: int) -> int:
    inventory = inventory_map(data, kind)
    key = str(entry_id)
    current = inventory.get(key, 0)
    if not isinstance(current, int):
        current = 0
    updated = current + delta
    if updated <= 0:
        inventory.pop(key, None)
        return 0
    inventory[key] = updated
    return updated
