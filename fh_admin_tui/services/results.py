from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MutationResult:
    changed: bool
    message: str
    severity: str = "information"


@dataclass(frozen=True)
class QuantityMutationResult(MutationResult):
    updated_quantity: int = 0


@dataclass(frozen=True)
class ActionAvailability:
    enabled: bool
    reason: str = ""
