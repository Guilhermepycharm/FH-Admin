from __future__ import annotations

from fh_admin_tui.catalog import Catalog, Entry
from fh_admin_tui.mutations import add_quantity, list_owned_entries, set_quantity
from fh_admin_tui.services.results import QuantityMutationResult


class InventoryService:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def current_quantity(self, data: dict, kind: str, entry_id: int) -> int:
        return next((owned.quantity for owned in list_owned_entries(data, kind) if owned.entry_id == entry_id), 0)

    def entry_name(self, kind: str, entry_id: int) -> str:
        return self.entry(kind, entry_id).name

    def entry(self, kind: str, entry_id: int) -> Entry:
        return self.catalog.entries_for_kind(kind).get(entry_id, Entry(entry_id, f"ID {entry_id}", ""))

    def add_entry(self, data: dict, kind: str, entry_id: int, quantity: int) -> QuantityMutationResult:
        updated = add_quantity(data, kind, entry_id, quantity)
        name = self.entry_name(kind, entry_id)
        return QuantityMutationResult(True, f"{name} ajustado em {quantity}.", updated_quantity=updated)

    def mutate_selected(
        self,
        data: dict,
        kind: str,
        entry_id: int,
        mode: str,
        quantity: int | None = None,
    ) -> QuantityMutationResult:
        name = self.entry_name(kind, entry_id)
        before = self.current_quantity(data, kind, entry_id)
        if mode == "delete":
            if before <= 0:
                return QuantityMutationResult(False, f"{name} ja nao esta no inventario.", "warning", 0)
            set_quantity(data, kind, entry_id, 0)
            return QuantityMutationResult(True, f"{name} removido.", updated_quantity=0)
        if quantity is None:
            raise ValueError("quantity e obrigatorio para set/plus/minus")
        if mode == "set":
            set_quantity(data, kind, entry_id, quantity)
            updated = quantity
        elif mode == "plus":
            updated = add_quantity(data, kind, entry_id, quantity)
        elif mode == "minus":
            updated = add_quantity(data, kind, entry_id, -quantity)
        else:
            raise ValueError(f"Modo de inventario invalido: {mode}")
        return QuantityMutationResult(before != updated, f"{name} agora esta em {updated}.", updated_quantity=updated)
