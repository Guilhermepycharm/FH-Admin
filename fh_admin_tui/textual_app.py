from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from textual import on
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, ListItem, ListView, Static, TabbedContent

from .catalog import Catalog
from .config import AppConfig
from .diagnostics import LOG_PATH, get_logger
from .controllers.textual_actions import TextualActionController
from .save_ops import SaveRepository, SaveSession, SaveSlot
from .services.actor_service import ActorService
from .services.inventory_service import InventoryService
from .ui.layout import APP_BINDINGS, APP_CSS, PANEL_TITLES, compose_main_layout, setup_editor_tables
from .ui.rendering import (
    actor_detail_text,
    actor_rows,
    inventory_detail_text,
    inventory_rows,
    slot_meta_text,
    staged_detail_text,
    summary_text,
)
from .ui.screens import ConfirmScreen

logger = get_logger("textual")

class FearHungerTextualApp(App[None]):
    CSS = APP_CSS
    BINDINGS = APP_BINDINGS

    def __init__(self, repo: SaveRepository | None = None, catalog: Catalog | None = None) -> None:
        super().__init__()
        self.repo = repo or SaveRepository()
        self.catalog = catalog or Catalog.load(self.repo.data_dir)
        self.actor_service = ActorService(self.catalog)
        self.inventory_service = InventoryService(self.catalog)
        self.actions = TextualActionController(self, self.actor_service, self.inventory_service)
        self.slots: list[SaveSlot] = []
        self.slot_lookup: dict[str, SaveSlot] = {}
        self.session: SaveSession | None = None
        self.current_slot_key: str | None = None
        self.inventory_selection: dict[str, int | None] = {"items": None, "weapons": None, "armors": None}
        self.actor_selection: int | None = None
        self.operation_in_progress = False

    def compose(self) -> ComposeResult:
        yield from compose_main_layout()

    def on_mount(self) -> None:
        setup_editor_tables(self)
        self._update_actions_visibility()
        self.call_after_refresh(lambda: self._start_flow(self._initial_load_flow, "carregar saves"))

    def on_unmount(self) -> None:
        if self.operation_in_progress:
            logger.warning("Encerramento durante operacao; limpeza temporaria delegada ao processo")
            return
        if self.session is not None:
            try:
                self.session.close()
            except OSError:
                logger.exception("Falha ao limpar a sessao temporaria no encerramento")
            self.session = None

    def refresh_slots(self) -> None:
        self._render_slots(self.repo.list_slots())

    def _render_slots(self, slots: list[SaveSlot]) -> None:
        self.slots = slots
        self.slot_lookup = {}
        list_view = self.query_one("#slots", ListView)
        list_view.clear()
        for slot in self.slots:
            key = f"file{slot.number}"
            self.slot_lookup[key] = slot
            list_view.append(ListItem(Label(f"file{slot.number}.rpgsave"), id=key))
        if self.slots:
            list_view.index = 0
            self._update_slot_meta(self.slots[0])
        else:
            self.query_one("#slot-meta", Static).update("Nenhum save encontrado.")

    async def _initial_load_flow(self) -> None:
        slots = await asyncio.to_thread(self.repo.list_slots)
        self._render_slots(slots)
        if slots:
            await self._open_selected_slot()

    def action_reload_slots(self) -> None:
        self._start_flow(self._reload_slots_flow, "recarregar slots")

    def action_show_help(self) -> None:
        self.notify("Ctrl+S apply, Ctrl+B backup, Ctrl+R recarregar, F5 atualizar slots.")

    async def _await_screen_result(self, screen):
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def callback(result) -> None:
            if not future.done():
                loop.call_soon(future.set_result, result)

        self.push_screen(screen, callback=callback)
        return await future

    def _start_flow(self, flow: Callable[[], Awaitable[None]], label: str) -> None:
        if self.operation_in_progress:
            self.notify("Aguarde a operacao atual terminar.", severity="warning")
            return
        self.operation_in_progress = True
        self._set_operation_status(f"Executando: {label}...")
        self._update_actions_visibility()
        self.run_worker(self._guard_flow(flow, label), exclusive=False, name=label)

    async def _guard_flow(self, flow: Callable[[], Awaitable[None]], label: str) -> None:
        logger.info("Inicio da operacao: %s", label)
        failed = False
        try:
            await flow()
        except asyncio.CancelledError:
            logger.info("Operacao cancelada: %s", label)
            raise
        except Exception as exc:
            failed = True
            logger.exception("Falha na operacao: %s", label)
            self._set_operation_status(f"Falha: {label}")
            self.notify(
                f"Falha ao {label}: {exc}. Detalhes em {LOG_PATH}",
                title="Erro",
                severity="error",
                timeout=10,
            )
        finally:
            self.operation_in_progress = False
            if not failed:
                self._set_operation_status("Pronto.")
            try:
                self._update_actions_visibility()
            except (IndexError, NoMatches):
                logger.info("Tela principal ja foi desmontada ao finalizar: %s", label)
            logger.info("Fim da operacao: %s", label)

    def _set_operation_status(self, message: str) -> None:
        try:
            self.screen_stack[0].query_one("#operation-status", Static).update(message)
        except (IndexError, NoMatches):
            logger.debug("Status ignorado porque a tela principal nao esta montada")

    async def _reload_slots_flow(self) -> None:
        slots = await asyncio.to_thread(self.repo.list_slots)
        self._render_slots(slots)
        self.notify("Lista de slots recarregada.")

    def action_request_quit(self) -> None:
        self._start_flow(self._quit_flow, "sair")

    async def _quit_flow(self) -> None:
        if self.session is not None and self.session.dirty:
            confirmed = await self._await_screen_result(ConfirmScreen("Sair e perder alteracoes staged?"))
            if not confirmed:
                return
        if self.session is not None:
            await asyncio.to_thread(self.session.close)
            self.session = None
        self.exit()

    def action_backup_current(self) -> None:
        self._start_flow(self._backup_current_flow, "criar backup")

    async def _backup_current_flow(self) -> None:
        slot = self._selected_slot()
        if slot is None:
            self.notify("Nenhum slot selecionado.", severity="warning")
            return
        backup = await asyncio.to_thread(self.repo.create_backup, slot)
        self.notify(f"Backup criado: {backup.name}")

    def action_reload_session(self) -> None:
        self._start_flow(self._reload_session_flow, "recarregar slot")

    async def _reload_session_flow(self) -> None:
        if self.session is None:
            return
        if self.session.dirty:
            confirmed = await self._await_screen_result(ConfirmScreen("Descartar alteracoes staged e recarregar?"))
            if not confirmed:
                return
        await asyncio.to_thread(self.session.reload)
        self._refresh_all_views()
        self.notify("Sessao recarregada do save original.")

    def action_apply_changes(self) -> None:
        self._start_flow(self.actions.review_and_apply, "aplicar alteracoes")

    @on(ListView.Selected, "#slots")
    def slot_selected(self, event: ListView.Selected) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        if event.item and event.item.id and event.item.id in self.slot_lookup:
            self._update_slot_meta(self.slot_lookup[event.item.id])

    @on(ListView.Highlighted, "#slots")
    def slot_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        if event.item and event.item.id and event.item.id in self.slot_lookup:
            self._update_slot_meta(self.slot_lookup[event.item.id])

    @on(Button.Pressed, "#open-slot")
    def open_slot_button(self) -> None:
        self._start_flow(self._open_selected_slot, "abrir slot")

    @on(Button.Pressed, "#backup-slot")
    def backup_slot_button(self) -> None:
        self.action_backup_current()

    @on(Button.Pressed, "#restore-slot")
    def restore_slot_button(self) -> None:
        self._start_flow(self.actions.restore_backup, "restaurar backup")

    @on(Button.Pressed, "#refresh-slots")
    def refresh_slots_button(self) -> None:
        self.action_reload_slots()

    @on(TabbedContent.TabActivated, "#tabs")
    def tab_changed(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self._update_actions_visibility()
        self._refresh_detail_panel()

    @on(DataTable.RowHighlighted)
    def table_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if isinstance(self.screen, ModalScreen) or event.data_table.id not in {
            "items-table",
            "weapons-table",
            "armors-table",
            "actors-table",
        }:
            return
        self._store_selection(event.data_table)
        self._refresh_detail_panel()
        self._update_actions_visibility()

    @on(DataTable.RowSelected)
    def table_selected(self, event: DataTable.RowSelected) -> None:
        if isinstance(self.screen, ModalScreen) or event.data_table.id not in {
            "items-table",
            "weapons-table",
            "armors-table",
            "actors-table",
        }:
            return
        self._store_selection(event.data_table)
        self._refresh_detail_panel()
        self._update_actions_visibility()

    @on(Button.Pressed, "#action-add")
    def add_entry(self) -> None:
        self._start_flow(self.actions.add_entry_flow, "adicionar entrada")

    @on(Button.Pressed, "#action-set")
    def set_entry(self) -> None:
        self._start_flow(lambda: self.actions.mutate_inventory("set"), "definir quantidade")

    @on(Button.Pressed, "#action-plus")
    def plus_entry(self) -> None:
        self._start_flow(lambda: self.actions.mutate_inventory("plus"), "somar quantidade")

    @on(Button.Pressed, "#action-minus")
    def minus_entry(self) -> None:
        self._start_flow(lambda: self.actions.mutate_inventory("minus"), "subtrair quantidade")

    @on(Button.Pressed, "#action-delete")
    def delete_entry(self) -> None:
        self._start_flow(lambda: self.actions.mutate_inventory("delete"), "remover entrada")

    @on(Button.Pressed, "#action-skill")
    def actor_add_skill(self) -> None:
        self._start_flow(self.actions.actor_add_skill_flow, "adicionar skill")

    @on(Button.Pressed, "#action-revive")
    def actor_revive(self) -> None:
        self._start_flow(self.actions.actor_revive_flow, "reviver personagem")

    @on(Button.Pressed, "#action-infection")
    def actor_infection(self) -> None:
        self._start_flow(self.actions.actor_infection_flow, "curar infeccao")

    @on(Button.Pressed, "#action-arms")
    def actor_arms(self) -> None:
        self._start_flow(self.actions.actor_arms_flow, "restaurar membros")

    @on(Button.Pressed, "#action-wounds")
    def actor_wounds(self) -> None:
        self._start_flow(self.actions.actor_wounds_flow, "curar ferimentos")

    @on(Button.Pressed, "#action-party")
    def actor_party(self) -> None:
        self._start_flow(self.actions.actor_party_flow, "adicionar a party")

    @on(Button.Pressed, "#action-unequip")
    def actor_unequip(self) -> None:
        self._start_flow(self.actions.actor_unequip_flow, "desequipar armor")

    @on(Button.Pressed, "#action-apply")
    def action_apply_button(self) -> None:
        self.action_apply_changes()

    async def _open_selected_slot(self) -> None:
        slot = self._selected_slot()
        if slot is None:
            self.notify("Nenhum slot selecionado.", severity="warning")
            return
        if self.current_slot_key == f"file{slot.number}" and self.session is not None:
            return
        if self.session is not None and self.session.dirty:
            confirmed = await self._await_screen_result(ConfirmScreen("Trocar de slot e perder alteracoes staged?"))
            if not confirmed:
                return
        new_session = await asyncio.to_thread(self.repo.open_session, slot)
        old_session = self.session
        self._install_session(new_session)
        if old_session is not None:
            await asyncio.to_thread(old_session.close)
        self.notify(f"Slot {slot.number} aberto.")

    def _install_session(self, session: SaveSession) -> None:
        self.session = session
        self.current_slot_key = f"file{session.slot.number}"
        self.inventory_selection = {"items": None, "weapons": None, "armors": None}
        self.actor_selection = None
        self._refresh_all_views()

    def _refresh_all_views(self) -> None:
        self._refresh_summary()
        self._refresh_inventory_table("items")
        self._refresh_inventory_table("weapons")
        self._refresh_inventory_table("armors")
        self._refresh_actors_table()
        self._refresh_detail_panel()
        self._update_actions_visibility()

    def _refresh_summary(self) -> None:
        self.query_one("#summary-view", Static).update(summary_text(self.session, self.catalog))

    def _refresh_inventory_table(self, kind: str) -> None:
        table = self.query_one(f"#{kind}-table", DataTable)
        table.clear(columns=False)
        for row in inventory_rows(self.session, self.catalog, kind):
            table.add_row(*row, key=row[0])
        selected = self.inventory_selection.get(kind)
        if selected is not None:
            self._restore_table_cursor(table, str(selected))

    def _refresh_actors_table(self) -> None:
        table = self.query_one("#actors-table", DataTable)
        table.clear(columns=False)
        for row in actor_rows(self.session, self.catalog, self._actor_list()):
            table.add_row(*row, key=row[0])
        if self.actor_selection is not None:
            self._restore_table_cursor(table, str(self.actor_selection))

    def _refresh_detail_panel(self) -> None:
        detail = self.query_one("#detail-view", Static)
        if self.session is None:
            detail.update("Nenhum slot aberto.")
            return
        panel = self._current_panel()
        if panel in {"items", "weapons", "armors"}:
            detail.update(inventory_detail_text(self.session, self.catalog, panel, self.inventory_selection.get(panel)))
            return
        if panel == "actors":
            detail.update(actor_detail_text(self.session, self.catalog, self._selected_actor_id()))
            return
        detail.update(staged_detail_text(self.session, self.catalog))

    def _update_actions_visibility(self) -> None:
        root = self.screen_stack[0]
        panel = self._current_panel()
        inventory_actions = {"action-add", "action-set", "action-plus", "action-minus", "action-delete"}
        actor_actions = {
            "action-skill",
            "action-revive",
            "action-infection",
            "action-wounds",
            "action-arms",
            "action-party",
            "action-unequip",
        }
        all_actions = inventory_actions | actor_actions | {"action-apply"}
        for action_id in all_actions:
            button = root.query_one(f"#{action_id}", Button)
            button.display = False
        if panel in {"items", "weapons", "armors"}:
            for action_id in inventory_actions:
                root.query_one(f"#{action_id}", Button).display = True
        elif panel == "actors":
            for action_id in actor_actions:
                root.query_one(f"#{action_id}", Button).display = True
        apply_button = root.query_one("#action-apply", Button)
        apply_button.display = self.session is not None

        has_session = self.session is not None
        selected_inventory = panel in self.inventory_selection and self.inventory_selection.get(panel) is not None
        selected_actor = self.actor_selection is not None
        for action_id in ("action-set", "action-plus", "action-minus", "action-delete"):
            root.query_one(f"#{action_id}", Button).disabled = self.operation_in_progress or not selected_inventory
        root.query_one("#action-add", Button).disabled = self.operation_in_progress or not has_session
        for action_id in (
            "action-skill",
            "action-revive",
            "action-infection",
            "action-wounds",
            "action-arms",
            "action-party",
            "action-unequip",
        ):
            root.query_one(f"#{action_id}", Button).disabled = self.operation_in_progress or not selected_actor
        if has_session and selected_actor:
            assert self.session is not None
            assert self.actor_selection is not None
            limb_state = self.actor_service.limb_restore_action_state(self.actor_selection)
            party_state = self.actor_service.party_action_state(self.session.data, self.actor_selection)
            root.query_one("#action-arms", Button).disabled = self.operation_in_progress or not limb_state.enabled
            root.query_one("#action-party", Button).disabled = self.operation_in_progress or not party_state.enabled
        apply_button.disabled = self.operation_in_progress or not has_session or not bool(self.session and self.session.dirty)
        for action_id in ("open-slot", "backup-slot", "restore-slot", "refresh-slots"):
            root.query_one(f"#{action_id}", Button).disabled = self.operation_in_progress
        root.query_one("#slots", ListView).disabled = self.operation_in_progress

    def _selected_slot(self) -> SaveSlot | None:
        list_view = self.query_one("#slots", ListView)
        highlighted = list_view.highlighted_child
        if highlighted is None or highlighted.id is None:
            return None
        return self.slot_lookup.get(highlighted.id)

    def _selected_actor_id(self) -> int | None:
        return self.actor_selection

    def _current_panel(self) -> str:
        return self.screen_stack[0].query_one("#tabs", TabbedContent).active or "summary"

    def _actor_list(self) -> list[int]:
        if self.session is None:
            return []
        return self.actor_service.sorted_actor_ids(self.session.data)

    def _store_selection(self, table: DataTable) -> None:
        if table.row_count == 0 or table.cursor_row < 0:
            return
        cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        value = int(str(cell_key.row_key.value))
        if table.id == "actors-table":
            self.actor_selection = value
        elif table.id == "items-table":
            self.inventory_selection["items"] = value
        elif table.id == "weapons-table":
            self.inventory_selection["weapons"] = value
        elif table.id == "armors-table":
            self.inventory_selection["armors"] = value

    def _restore_table_cursor(self, table: DataTable, key: str) -> None:
        for index in range(table.row_count):
            cell_key = table.coordinate_to_cell_key(Coordinate(index, 0))
            if str(cell_key.row_key.value) == key:
                table.move_cursor(row=index)
                break

    def _update_slot_meta(self, slot: SaveSlot) -> None:
        try:
            modified = slot.path.stat().st_mtime
            backups = self.repo.list_backups(slot)
        except OSError:
            modified = 0
            backups = []
        self.query_one("#slot-meta", Static).update(slot_meta_text(slot, backups, modified))

def main(config: AppConfig | None = None) -> int:
    repo = SaveRepository.from_config(config) if config is not None else None
    FearHungerTextualApp(repo=repo).run()
    return 0
