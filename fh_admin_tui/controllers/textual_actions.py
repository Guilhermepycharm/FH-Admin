from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from fh_admin_tui.catalog import Entry
from fh_admin_tui.services.actor_service import ActorService
from fh_admin_tui.services.inventory_service import InventoryService
from fh_admin_tui.services.results import MutationResult
from fh_admin_tui.services.review_service import build_review
from fh_admin_tui.ui.layout import PANEL_TITLES
from fh_admin_tui.ui.screens import ChoiceScreen, ConfirmScreen, ReviewScreen, SearchChoice, TextInputScreen

if TYPE_CHECKING:
    from fh_admin_tui.textual_app import FearHungerTextualApp


class TextualActionController:
    def __init__(self, app: FearHungerTextualApp, actor_service: ActorService, inventory_service: InventoryService) -> None:
        self.app = app
        self.actor_service = actor_service
        self.inventory_service = inventory_service

    async def actor_add_skill_flow(self) -> None:
        actor_id = self.app._selected_actor_id()
        if actor_id is None or self.app.session is None:
            return
        actor_name = self.actor_service.display_name(self.app.session.data, actor_id)
        query = await self.app._await_screen_result(TextInputScreen(f"Buscar skill para {actor_name}", placeholder="nome ou ID"))
        if not query:
            return
        entry = await self._choose_catalog_entry("skills", query)
        if entry is None:
            return
        self._handle_result(self.actor_service.add_skill(self.app.session.data, actor_id, entry.entry_id))

    async def actor_revive_flow(self) -> None:
        await self._run_actor_mutation(lambda data, actor_id: self.actor_service.revive(data, actor_id))

    async def actor_infection_flow(self) -> None:
        await self._run_actor_mutation(lambda data, actor_id: self.actor_service.cure_infection(data, actor_id))

    async def actor_arms_flow(self) -> None:
        await self._run_actor_mutation(lambda data, actor_id: self.actor_service.restore_limbs(data, actor_id))

    async def actor_wounds_flow(self) -> None:
        await self._run_actor_mutation(lambda data, actor_id: self.actor_service.heal_wounds(data, actor_id))

    async def actor_party_flow(self) -> None:
        await self._run_actor_mutation(lambda data, actor_id: self.actor_service.add_to_party(data, actor_id))

    async def actor_unequip_flow(self) -> None:
        actor_id = self.app._selected_actor_id()
        if actor_id is None or self.app.session is None:
            return
        choices = self.actor_service.equipped_armor_choices(self.app.session.data, actor_id)
        actor_name = self.actor_service.display_name(self.app.session.data, actor_id)
        if not choices:
            self.app.notify(f"{actor_name} nao tem armor equipada.", severity="warning")
            return
        search_choices = [SearchChoice(entry.entry_id, entry.name, "") for entry in choices]
        choice = await self.app._await_screen_result(ChoiceScreen(f"Desequipar de {actor_name}", search_choices))
        if choice is None:
            return
        self._handle_result(self.actor_service.unequip_armor(self.app.session.data, actor_id, choice.entry_id))

    async def add_entry_flow(self) -> None:
        panel = self.app._current_panel()
        if panel not in {"items", "weapons", "armors"} or self.app.session is None:
            return
        query = await self.app._await_screen_result(TextInputScreen(f"Buscar em {PANEL_TITLES[panel]}", placeholder="nome ou ID"))
        if not query:
            return
        entry = await self._choose_catalog_entry(panel, query)
        if entry is None:
            return
        quantity = await self._prompt_int("Quantidade inicial", 1, minimum=1)
        if quantity is None:
            return
        self._handle_result(self.inventory_service.add_entry(self.app.session.data, panel, entry.entry_id, quantity))

    async def mutate_inventory(self, mode: str) -> None:
        if self.app.session is None:
            return
        panel = self.app._current_panel()
        if panel not in {"items", "weapons", "armors"}:
            return
        entry_id = self.app.inventory_selection.get(panel)
        if entry_id is None:
            self.app.notify("Nenhuma entrada selecionada.", severity="warning")
            return
        entry = self.inventory_service.entry(panel, entry_id)
        if mode == "delete":
            confirmed = await self.app._await_screen_result(ConfirmScreen(f"Remover {entry.name} do inventario?"))
            if not confirmed:
                return
            self._handle_result(self.inventory_service.mutate_selected(self.app.session.data, panel, entry_id, "delete"))
            return
        title = {
            "set": f"Quantidade exata para {entry.name}",
            "plus": f"Somar quantidade em {entry.name}",
            "minus": f"Subtrair quantidade de {entry.name}",
        }[mode]
        current_qty = self.inventory_service.current_quantity(self.app.session.data, panel, entry_id)
        quantity = await self._prompt_int(title, current_qty if mode == "set" else 1, minimum=0 if mode == "set" else 1)
        if quantity is None:
            return
        self._handle_result(self.inventory_service.mutate_selected(self.app.session.data, panel, entry_id, mode, quantity))

    async def restore_backup(self) -> None:
        slot = self.app._selected_slot()
        if slot is None:
            return
        backups = self.app.repo.list_backups(slot)
        if not backups:
            self.app.notify(f"Nenhum backup encontrado para file{slot.number}.", severity="warning")
            return
        choices = [SearchChoice(index, path.name, str(path)) for index, path in enumerate(backups)]
        chosen = await self.app._await_screen_result(ChoiceScreen(f"Restaurar backup de file{slot.number}", choices))
        if chosen is None:
            return
        confirmed = await self.app._await_screen_result(ConfirmScreen(f"Restaurar {chosen.name} em file{slot.number}?"))
        if not confirmed:
            return
        safety = await asyncio.to_thread(self.app.repo.restore_backup, slot, backups[chosen.entry_id])
        if self.app.session is not None and self.app.current_slot_key == f"file{slot.number}":
            await asyncio.to_thread(self.app.session.reload)
            self.app._refresh_all_views()
        self.app.notify(f"Backup restaurado. Save anterior salvo em {safety.name}.")

    async def review_and_apply(self) -> None:
        if self.app.session is None:
            return
        if not self.app.session.dirty:
            self.app.notify("Nao ha alteracoes staged.", severity="warning")
            return
        review = build_review(self.app.session.baseline, self.app.session.data, self.app.catalog)
        confirmed = await self.app._await_screen_result(ReviewScreen(review.lines, review.errors))
        if not confirmed:
            return
        backup = await asyncio.to_thread(self.app.session.apply)
        self.app._refresh_all_views()
        self.app.notify(f"Alteracoes aplicadas. Backup: {backup.name}")

    async def _run_actor_mutation(self, operation) -> None:
        actor_id = self.app._selected_actor_id()
        if actor_id is None or self.app.session is None:
            return
        self._handle_result(operation(self.app.session.data, actor_id))

    def _handle_result(self, result: MutationResult) -> None:
        if result.changed:
            assert self.app.session is not None
            self.app.session.mark_dirty()
            self.app._refresh_all_views()
        self.app.notify(result.message, severity=result.severity)

    async def _choose_catalog_entry(self, kind: str, query: str) -> Entry | None:
        matches = self.app.catalog.search(kind, query)
        if not matches:
            self.app.notify("Nenhum resultado.", severity="warning")
            return None
        choices = [SearchChoice(entry.entry_id, entry.name, entry.description) for entry in matches]
        chosen = await self.app._await_screen_result(ChoiceScreen(f"Escolha em {PANEL_TITLES.get(kind, kind)}", choices))
        if chosen is None:
            return None
        return self.app.catalog.entries_for_kind(kind)[chosen.entry_id]

    async def _prompt_int(self, title: str, default: int, minimum: int | None = None) -> int | None:
        value = await self.app._await_screen_result(TextInputScreen(title, value=str(default)))
        if value is None:
            return None
        try:
            parsed = int(value)
        except ValueError:
            self.app.notify("Numero invalido.", severity="error")
            return None
        if minimum is not None and parsed < minimum:
            self.app.notify(f"Use um numero maior ou igual a {minimum}.", severity="error")
            return None
        return parsed
