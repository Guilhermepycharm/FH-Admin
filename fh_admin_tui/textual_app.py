from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.css.query import NoMatches
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, ListItem, ListView, Static, TabbedContent, TabPane

from .catalog import Catalog, Entry
from .diagnostics import LOG_PATH, get_logger
from .mutations import (
    LIMB_REPAIR_CONFIG,
    actor_display_name,
    actor_ids,
    actor_status_lines,
    add_actor_to_party,
    add_quantity,
    add_skill,
    cure_infections,
    diff_summary_lines,
    equipped_armor_ids,
    heal_physical_conditions,
    list_owned_entries,
    party_actor_ids,
    restore_supported_limbs,
    revive_actor,
    set_quantity,
    unequip_armor,
    validate_data,
)
from .save_ops import SaveRepository, SaveSession, SaveSlot


logger = get_logger("textual")


PANEL_TITLES = {
    "summary": "Resumo",
    "items": "Itens",
    "weapons": "Armas",
    "armors": "Armaduras",
    "actors": "Atores",
}


@dataclass
class SearchChoice:
    entry_id: int
    name: str
    description: str


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "dismiss_false", "Cancelar")]
    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-box {
        width: 70;
        max-width: 90%;
        height: auto;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }
    #confirm-buttons {
        layout: horizontal;
        align-horizontal: right;
        margin-top: 1;
    }
    Button {
        margin-left: 1;
    }
    """

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.question)
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancelar", id="cancel")
                yield Button("Confirmar", id="confirm", variant="primary")

    def on_mount(self) -> None:
        self.call_after_refresh(lambda: self.query_one("#confirm", Button).focus())

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#confirm")
    def confirm(self) -> None:
        self.dismiss(True)

    def action_dismiss_false(self) -> None:
        self.dismiss(False)


class TextInputScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "dismiss_none", "Cancelar")]
    CSS = """
    TextInputScreen {
        align: center middle;
    }
    #input-box {
        width: 80;
        max-width: 92%;
        height: auto;
        padding: 1 2;
        border: solid $accent;
        background: $surface;
    }
    #input-actions {
        layout: horizontal;
        align-horizontal: right;
        margin-top: 1;
    }
    Button {
        margin-left: 1;
    }
    """

    def __init__(self, title: str, value: str = "", placeholder: str = "") -> None:
        super().__init__()
        self.title = title
        self.value = value
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="input-box"):
            yield Label(self.title)
            yield Input(value=self.value, placeholder=self.placeholder, id="prompt-input")
            with Horizontal(id="input-actions"):
                yield Button("Cancelar", id="cancel")
                yield Button("OK", id="confirm", variant="primary")

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_input)

    def _focus_input(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#prompt-input")
    def submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#confirm")
    def confirm(self) -> None:
        value = self.query_one("#prompt-input", Input).value.strip()
        self.dismiss(value or None)


class ChoiceScreen(ModalScreen[SearchChoice | None]):
    BINDINGS = [Binding("escape", "dismiss_none", "Cancelar")]
    CSS = """
    ChoiceScreen {
        align: center middle;
    }
    #choice-box {
        width: 110;
        max-width: 96%;
        height: 75%;
        border: solid $primary;
        background: $surface;
    }
    #choice-table {
        height: 1fr;
    }
    #choice-description {
        height: 7;
        padding: 1;
        border-top: solid $panel;
    }
    #choice-actions {
        layout: horizontal;
        align-horizontal: right;
        padding: 0 1 1 1;
    }
    Button {
        margin-left: 1;
    }
    """

    def __init__(self, title: str, choices: list[SearchChoice]) -> None:
        super().__init__()
        self.title = title
        self.choices = choices

    def compose(self) -> ComposeResult:
        with Vertical(id="choice-box"):
            yield Label(self.title)
            yield DataTable(id="choice-table")
            yield Static("", id="choice-description")
            with Horizontal(id="choice-actions"):
                yield Button("Cancelar", id="cancel")
                yield Button("Escolher", id="confirm", variant="primary")

    def on_mount(self) -> None:
        table = self.query_one("#choice-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Nome", "Descricao")
        for choice in self.choices:
            table.add_row(str(choice.entry_id), choice.name, choice.description[:80], key=str(choice.entry_id))
        self.call_after_refresh(self._focus_table)
        self._refresh_description()

    def _focus_table(self) -> None:
        self.query_one("#choice-table", DataTable).focus()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    @on(DataTable.RowHighlighted, "#choice-table")
    def row_highlighted(self) -> None:
        self._refresh_description()

    @on(DataTable.RowSelected, "#choice-table")
    def row_selected(self) -> None:
        self._choose_current()

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#confirm")
    def confirm(self) -> None:
        self._choose_current()

    def _current_choice(self) -> SearchChoice | None:
        table = self.query_one("#choice-table", DataTable)
        if table.row_count == 0 or table.cursor_row < 0:
            return None
        cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        row_key = str(cell_key.row_key.value)
        return next((choice for choice in self.choices if str(choice.entry_id) == row_key), None)

    def _refresh_description(self) -> None:
        choice = self._current_choice()
        description = choice.description if choice else ""
        self.query_one("#choice-description", Static).update(description or "Sem descricao.")

    def _choose_current(self) -> None:
        self.dismiss(self._current_choice())


class ReviewScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "dismiss_false", "Cancelar")]
    CSS = """
    ReviewScreen {
        align: center middle;
    }
    #review-box {
        width: 120;
        max-width: 96%;
        height: 80%;
        border: solid $warning;
        background: $surface;
    }
    #review-body {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    #review-actions {
        layout: horizontal;
        align-horizontal: right;
        padding: 0 1 1 1;
    }
    Button {
        margin-left: 1;
    }
    """

    def __init__(self, lines: list[str], errors: list[str]) -> None:
        super().__init__()
        self.lines = lines
        self.errors = errors

    def compose(self) -> ComposeResult:
        with Vertical(id="review-box"):
            yield Label("Revisao antes do apply")
            yield Static(id="review-body")
            with Horizontal(id="review-actions"):
                yield Button("Cancelar", id="cancel")
                yield Button("Confirmar apply", id="confirm", variant="primary", disabled=bool(self.errors))

    def on_mount(self) -> None:
        body = "\n".join(self.lines)
        if self.errors:
            body += "\n\nErros de validacao:\n" + "\n".join(f"- {error}" for error in self.errors)
        self.query_one("#review-body", Static).update(body or "Nenhuma alteracao.")
        target = "#cancel" if self.errors else "#confirm"
        self.call_after_refresh(lambda: self.query_one(target, Button).focus())

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#confirm")
    def confirm(self) -> None:
        self.dismiss(True)

    def action_dismiss_false(self) -> None:
        self.dismiss(False)


class FearHungerTextualApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }
    #workspace {
        layout: horizontal;
        height: 1fr;
    }
    #sidebar {
        width: 28;
        min-width: 24;
        border-right: solid $panel;
    }
    #sidebar-buttons {
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        padding: 1;
    }
    #main-pane {
        width: 1fr;
    }
    #detail-pane {
        width: 40;
        min-width: 30;
        border-left: solid $panel;
    }
    .panel-title {
        padding: 0 1;
        text-style: bold;
        color: $accent;
    }
    #slots {
        height: 1fr;
        padding: 0 1;
    }
    #tabs {
        height: 1fr;
    }
    .table-card {
        height: 1fr;
    }
    #summary-view, #detail-view, #actions-view {
        padding: 1;
    }
    #detail-view {
        height: 1fr;
        overflow-y: auto;
    }
    #actions-view Button {
        width: 100%;
        margin-bottom: 1;
    }
    #actions-view {
        overflow-y: auto;
    }
    #slot-meta {
        padding: 1;
        border-top: solid $panel;
    }
    #operation-status {
        padding: 0 1 1 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "request_quit", "Sair"),
        Binding("f5", "reload_slots", "Recarregar slots"),
        Binding("ctrl+b", "backup_current", "Backup"),
        Binding("ctrl+r", "reload_session", "Recarregar slot"),
        Binding("ctrl+s", "apply_changes", "Apply"),
        Binding("?", "show_help", "Ajuda"),
    ]

    def __init__(self, repo: SaveRepository | None = None, catalog: Catalog | None = None) -> None:
        super().__init__()
        self.repo = repo or SaveRepository()
        self.catalog = catalog or Catalog.load(self.repo.data_dir)
        self.slots: list[SaveSlot] = []
        self.slot_lookup: dict[str, SaveSlot] = {}
        self.session: SaveSession | None = None
        self.current_slot_key: str | None = None
        self.inventory_selection: dict[str, int | None] = {"items": None, "weapons": None, "armors": None}
        self.actor_selection: int | None = None
        self.operation_in_progress = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="workspace"):
            with Vertical(id="sidebar"):
                yield Label("Slots", classes="panel-title")
                yield ListView(id="slots")
                with Horizontal(id="sidebar-buttons"):
                    yield Button("Abrir", id="open-slot", variant="primary")
                    yield Button("Backup", id="backup-slot")
                    yield Button("Restaurar", id="restore-slot")
                    yield Button("Atualizar", id="refresh-slots")
                yield Static("", id="slot-meta")
            with Vertical(id="main-pane"):
                yield Label("Editor", classes="panel-title")
                with TabbedContent(id="tabs", initial="summary"):
                    with TabPane("Resumo", id="summary"):
                        yield Static("Selecione um slot para começar.", id="summary-view")
                    with TabPane("Itens", id="items"):
                        yield DataTable(id="items-table", classes="table-card")
                    with TabPane("Armas", id="weapons"):
                        yield DataTable(id="weapons-table", classes="table-card")
                    with TabPane("Armaduras", id="armors"):
                        yield DataTable(id="armors-table", classes="table-card")
                    with TabPane("Atores", id="actors"):
                        yield DataTable(id="actors-table", classes="table-card")
            with Vertical(id="detail-pane"):
                yield Label("Detalhes", classes="panel-title")
                yield Static("Nenhum slot aberto.", id="detail-view")
                yield Label("Acoes", classes="panel-title")
                with Vertical(id="actions-view"):
                    yield Static("Pronto.", id="operation-status")
                    yield Button("Adicionar entrada", id="action-add", variant="primary")
                    yield Button("Definir quantidade", id="action-set")
                    yield Button("Somar quantidade", id="action-plus")
                    yield Button("Subtrair quantidade", id="action-minus")
                    yield Button("Remover entrada", id="action-delete")
                    yield Button("Adicionar skill", id="action-skill")
                    yield Button("Reviver ator", id="action-revive")
                    yield Button("Curar infeccao", id="action-infection")
                    yield Button("Curar ferimentos", id="action-wounds")
                    yield Button("Restaurar membros", id="action-arms")
                    yield Button("Adicionar a party atual", id="action-party")
                    yield Button("Desequipar armadura", id="action-unequip")
                    yield Button("Aplicar alteracoes", id="action-apply", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        self._setup_tables()
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

    def _setup_tables(self) -> None:
        for table_id in ("items-table", "weapons-table", "armors-table"):
            table = self.query_one(f"#{table_id}", DataTable)
            table.cursor_type = "row"
            table.add_columns("ID", "Nome", "Qtd", "Descricao")
        actors = self.query_one("#actors-table", DataTable)
        actors.cursor_type = "row"
        actors.add_columns("ID", "Nome", "Party", "HP", "States")

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
        self._start_flow(self._review_and_apply, "aplicar alteracoes")

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
        self._start_flow(self._restore_backup, "restaurar backup")

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
        self._start_flow(self._add_entry_flow, "adicionar entrada")

    @on(Button.Pressed, "#action-set")
    def set_entry(self) -> None:
        self._start_flow(lambda: self._mutate_inventory("set"), "definir quantidade")

    @on(Button.Pressed, "#action-plus")
    def plus_entry(self) -> None:
        self._start_flow(lambda: self._mutate_inventory("plus"), "somar quantidade")

    @on(Button.Pressed, "#action-minus")
    def minus_entry(self) -> None:
        self._start_flow(lambda: self._mutate_inventory("minus"), "subtrair quantidade")

    @on(Button.Pressed, "#action-delete")
    def delete_entry(self) -> None:
        self._start_flow(lambda: self._mutate_inventory("delete"), "remover entrada")

    @on(Button.Pressed, "#action-skill")
    def actor_add_skill(self) -> None:
        self._start_flow(self._actor_add_skill_flow, "adicionar skill")

    async def _actor_add_skill_flow(self) -> None:
        actor_id = self._selected_actor_id()
        if actor_id is None or self.session is None:
            return
        actor_name = actor_display_name(self.session.data, self.catalog, actor_id)
        query = await self._await_screen_result(TextInputScreen(f"Buscar skill para {actor_name}", placeholder="nome ou ID"))
        if not query:
            return
        entry = await self._choose_catalog_entry("skills", query)
        if entry is None:
            return
        changed = add_skill(self.session.data, actor_id, entry.entry_id)
        if changed:
            self.session.mark_dirty()
            self._refresh_all_views()
            self.notify(f"Skill {entry.name} adicionada a {actor_name}.")
        else:
            self.notify(f"{actor_name} ja conhece {entry.name}.", severity="warning")

    @on(Button.Pressed, "#action-revive")
    def actor_revive(self) -> None:
        self._start_flow(self._actor_revive_flow, "reviver ator")

    async def _actor_revive_flow(self) -> None:
        actor_id = self._selected_actor_id()
        if actor_id is None or self.session is None:
            return
        actor_name = actor_display_name(self.session.data, self.catalog, actor_id)
        revive_actor(self.session.data, actor_id, clear_switches=(278,) if actor_id == 6 else ())
        self.session.mark_dirty()
        self._refresh_all_views()
        self.notify(f"{actor_name} revivido.")

    @on(Button.Pressed, "#action-infection")
    def actor_infection(self) -> None:
        self._start_flow(self._actor_infection_flow, "curar infeccao")

    async def _actor_infection_flow(self) -> None:
        actor_id = self._selected_actor_id()
        if actor_id is None or self.session is None:
            return
        actor_name = actor_display_name(self.session.data, self.catalog, actor_id)
        removed = cure_infections(self.session.data, actor_id)
        self.session.mark_dirty()
        self._refresh_all_views()
        self.notify(f"Infeccoes removidas de {actor_name}: {removed or 'nenhuma'}.")

    @on(Button.Pressed, "#action-arms")
    def actor_arms(self) -> None:
        self._start_flow(self._actor_arms_flow, "restaurar membros")

    async def _actor_arms_flow(self) -> None:
        actor_id = self._selected_actor_id()
        if actor_id is None or self.session is None:
            return
        actor_name = actor_display_name(self.session.data, self.catalog, actor_id)
        actor = self.session.data["actors"]["_data"]["@a"][actor_id]
        states_before = list(actor["_states"]["@a"])
        restored = restore_supported_limbs(self.session.data, actor_id)
        states_changed = states_before != actor["_states"]["@a"]
        if restored or states_changed:
            self.session.mark_dirty()
            self._refresh_all_views()
            self.notify(f"Membros restaurados em {actor_name}: {restored or 'estados corrigidos'}")
        else:
            self.notify(f"Nenhum membro ausente detectado para {actor_name}.", severity="warning")

    @on(Button.Pressed, "#action-wounds")
    def actor_wounds(self) -> None:
        self._start_flow(self._actor_wounds_flow, "curar ferimentos")

    async def _actor_wounds_flow(self) -> None:
        actor_id = self._selected_actor_id()
        if actor_id is None or self.session is None:
            return
        actor_name = actor_display_name(self.session.data, self.catalog, actor_id)
        removed = heal_physical_conditions(self.session.data, actor_id)
        if not removed:
            self.notify(f"Nenhum ferimento curavel detectado em {actor_name}.", severity="warning")
            return
        self.session.mark_dirty()
        self._refresh_all_views()
        names = [self.catalog.states[state_id].name for state_id in removed if state_id in self.catalog.states]
        self.notify(f"Ferimentos curados em {actor_name}: {', '.join(names)}")

    @on(Button.Pressed, "#action-party")
    def actor_party(self) -> None:
        self._start_flow(self._actor_party_flow, "adicionar a party")

    async def _actor_party_flow(self) -> None:
        actor_id = self._selected_actor_id()
        if actor_id is None or self.session is None:
            return
        actor_name = actor_display_name(self.session.data, self.catalog, actor_id)
        if len(party_actor_ids(self.session.data)) >= 4 and actor_id not in party_actor_ids(self.session.data):
            self.notify("A party ja possui quatro membros.", severity="warning")
            return
        changed = add_actor_to_party(self.session.data, actor_id)
        if changed:
            self.session.mark_dirty()
            self._refresh_all_views()
            self.notify(f"{actor_name} adicionado a party.")
        else:
            self.notify(f"{actor_name} ja esta na party.", severity="warning")

    @on(Button.Pressed, "#action-unequip")
    def actor_unequip(self) -> None:
        self._start_flow(self._actor_unequip_flow, "desequipar armor")

    async def _actor_unequip_flow(self) -> None:
        actor_id = self._selected_actor_id()
        if actor_id is None or self.session is None:
            return
        equipped = equipped_armor_ids(self.session.data, actor_id)
        actor_name = actor_display_name(self.session.data, self.catalog, actor_id)
        if not equipped:
            self.notify(f"{actor_name} nao tem armor equipada.", severity="warning")
            return
        choices = [
            SearchChoice(armor_id, self.catalog.armors.get(armor_id, Entry(armor_id, f"Armor {armor_id}", "")).name, "")
            for armor_id in equipped
        ]
        choice = await self._await_screen_result(ChoiceScreen(f"Desequipar de {actor_name}", choices))
        if choice is None:
            return
        removed = unequip_armor(self.session.data, actor_id, choice.entry_id)
        if removed:
            self.session.mark_dirty()
            self._refresh_all_views()
            self.notify(f"{choice.name} removido de {actor_name}.")

    @on(Button.Pressed, "#action-apply")
    def action_apply_button(self) -> None:
        self.action_apply_changes()

    async def _add_entry_flow(self) -> None:
        panel = self._current_panel()
        if panel not in {"items", "weapons", "armors"} or self.session is None:
            return
        query = await self._await_screen_result(TextInputScreen(f"Buscar em {PANEL_TITLES[panel]}", placeholder="nome ou ID"))
        if not query:
            return
        entry = await self._choose_catalog_entry(panel, query)
        if entry is None:
            return
        quantity = await self._prompt_int("Quantidade inicial", 1, minimum=1)
        if quantity is None:
            return
        add_quantity(self.session.data, panel, entry.entry_id, quantity)
        self.session.mark_dirty()
        self._refresh_all_views()
        self.notify(f"{entry.name} ajustado em {quantity}.")

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

    async def _restore_backup(self) -> None:
        slot = self._selected_slot()
        if slot is None:
            return
        backups = self.repo.list_backups(slot)
        if not backups:
            self.notify(f"Nenhum backup encontrado para file{slot.number}.", severity="warning")
            return
        choices = [SearchChoice(index, path.name, str(path)) for index, path in enumerate(backups)]
        chosen = await self._await_screen_result(ChoiceScreen(f"Restaurar backup de file{slot.number}", choices))
        if chosen is None:
            return
        confirmed = await self._await_screen_result(ConfirmScreen(f"Restaurar {chosen.name} em file{slot.number}?"))
        if not confirmed:
            return
        safety = await asyncio.to_thread(self.repo.restore_backup, slot, backups[chosen.entry_id])
        if self.session is not None and self.current_slot_key == f"file{slot.number}":
            await asyncio.to_thread(self.session.reload)
            self._refresh_all_views()
        self.notify(f"Backup restaurado. Save anterior salvo em {safety.name}.")

    async def _review_and_apply(self) -> None:
        if self.session is None:
            return
        if not self.session.dirty:
            self.notify("Nao ha alteracoes staged.", severity="warning")
            return
        lines = diff_summary_lines(self.session.baseline, self.session.data, self.catalog)
        errors = validate_data(self.session.data)
        confirmed = await self._await_screen_result(ReviewScreen(lines, errors))
        if not confirmed:
            return
        backup = await asyncio.to_thread(self.session.apply)
        self._refresh_all_views()
        self.notify(f"Alteracoes aplicadas. Backup: {backup.name}")

    async def _mutate_inventory(self, mode: str) -> None:
        if self.session is None:
            return
        panel = self._current_panel()
        if panel not in {"items", "weapons", "armors"}:
            return
        entry_id = self.inventory_selection.get(panel)
        if entry_id is None:
            self.notify("Nenhuma entrada selecionada.", severity="warning")
            return
        entry = self.catalog.entries_for_kind(panel).get(entry_id, Entry(entry_id, f"ID {entry_id}", ""))
        current_qty = next((owned.quantity for owned in list_owned_entries(self.session.data, panel) if owned.entry_id == entry_id), 0)
        if mode == "delete":
            confirmed = await self._await_screen_result(ConfirmScreen(f"Remover {entry.name} do inventario?"))
            if not confirmed:
                return
            set_quantity(self.session.data, panel, entry_id, 0)
            self.session.mark_dirty()
            self._refresh_all_views()
            self.notify(f"{entry.name} removido.")
            return
        title = {
            "set": f"Quantidade exata para {entry.name}",
            "plus": f"Somar quantidade em {entry.name}",
            "minus": f"Subtrair quantidade de {entry.name}",
        }[mode]
        quantity = await self._prompt_int(
            title,
            current_qty if mode == "set" else 1,
            minimum=0 if mode == "set" else 1,
        )
        if quantity is None:
            return
        if mode == "set":
            set_quantity(self.session.data, panel, entry_id, quantity)
            updated = quantity
        elif mode == "plus":
            updated = add_quantity(self.session.data, panel, entry_id, quantity)
        else:
            updated = add_quantity(self.session.data, panel, entry_id, -quantity)
        self.session.mark_dirty()
        self._refresh_all_views()
        self.notify(f"{entry.name} agora esta em {updated}.")

    async def _choose_catalog_entry(self, kind: str, query: str) -> Entry | None:
        matches = self.catalog.search(kind, query)
        if not matches:
            self.notify("Nenhum resultado.", severity="warning")
            return None
        choices = [SearchChoice(entry.entry_id, entry.name, entry.description) for entry in matches]
        chosen = await self._await_screen_result(ChoiceScreen(f"Escolha em {PANEL_TITLES.get(kind, kind)}", choices))
        if chosen is None:
            return None
        return self.catalog.entries_for_kind(kind)[chosen.entry_id]

    async def _prompt_int(self, title: str, default: int, minimum: int | None = None) -> int | None:
        value = await self._await_screen_result(TextInputScreen(title, value=str(default)))
        if value is None:
            return None
        try:
            parsed = int(value)
        except ValueError:
            self.notify("Numero invalido.", severity="error")
            return None
        if minimum is not None and parsed < minimum:
            self.notify(f"Use um numero maior ou igual a {minimum}.", severity="error")
            return None
        return parsed

    def _refresh_all_views(self) -> None:
        self._refresh_summary()
        self._refresh_inventory_table("items")
        self._refresh_inventory_table("weapons")
        self._refresh_inventory_table("armors")
        self._refresh_actors_table()
        self._refresh_detail_panel()
        self._update_actions_visibility()

    def _refresh_summary(self) -> None:
        view = self.query_one("#summary-view", Static)
        if self.session is None:
            view.update("Selecione um slot para começar.")
            return
        slot = self.session.slot
        lines = [f"Slot: file{slot.number}.rpgsave", f"Alterado: {'sim' if self.session.dirty else 'nao'}", ""]
        lines.append("Party atual:")
        for actor_id in party_actor_ids(self.session.data):
            lines.append(f"- {actor_display_name(self.session.data, self.catalog, actor_id)} (ID {actor_id})")
        lines.extend(
            [
                "",
                f"Itens: {len(list_owned_entries(self.session.data, 'items'))}",
                f"Armas: {len(list_owned_entries(self.session.data, 'weapons'))}",
                f"Armaduras: {len(list_owned_entries(self.session.data, 'armors'))}",
            ]
        )
        errors = validate_data(self.session.data)
        lines.append("")
        lines.append("Validacao: OK" if not errors else "Validacao: com erros")
        if errors:
            lines.extend(f"- {error}" for error in errors[:8])
        view.update("\n".join(lines))

    def _refresh_inventory_table(self, kind: str) -> None:
        table = self.query_one(f"#{kind}-table", DataTable)
        table.clear(columns=False)
        if self.session is None:
            return
        for owned in list_owned_entries(self.session.data, kind):
            entry = self.catalog.entries_for_kind(kind).get(owned.entry_id, Entry(owned.entry_id, f"ID {owned.entry_id}", ""))
            table.add_row(str(owned.entry_id), entry.name, str(owned.quantity), entry.description[:64], key=str(owned.entry_id))
        selected = self.inventory_selection.get(kind)
        if selected is not None:
            self._restore_table_cursor(table, str(selected))

    def _refresh_actors_table(self) -> None:
        table = self.query_one("#actors-table", DataTable)
        table.clear(columns=False)
        if self.session is None:
            return
        for actor_id in self._actor_list():
            actor = self.session.data["actors"]["_data"]["@a"][actor_id]
            state_names = [
                self.catalog.states[state_id].name
                for state_id in actor["_states"]["@a"]
                if state_id in self.catalog.states and self.catalog.states[state_id].name
            ]
            table.add_row(
                str(actor_id),
                actor_display_name(self.session.data, self.catalog, actor_id),
                "sim" if actor_id in party_actor_ids(self.session.data) else "nao",
                str(actor.get("_hp", 0)),
                ", ".join(state_names[:3]) or "nenhum",
                key=str(actor_id),
            )
        if self.actor_selection is not None:
            self._restore_table_cursor(table, str(self.actor_selection))

    def _refresh_detail_panel(self) -> None:
        detail = self.query_one("#detail-view", Static)
        if self.session is None:
            detail.update("Nenhum slot aberto.")
            return
        panel = self._current_panel()
        if panel in {"items", "weapons", "armors"}:
            entry_id = self.inventory_selection.get(panel)
            if entry_id is None:
                detail.update("Selecione uma entrada.")
                return
            entry = self.catalog.entries_for_kind(panel).get(entry_id, Entry(entry_id, f"ID {entry_id}", ""))
            quantity = next((owned.quantity for owned in list_owned_entries(self.session.data, panel) if owned.entry_id == entry_id), 0)
            detail.update(f"ID: {entry.entry_id}\nNome: {entry.name}\nQtd: {quantity}\n\n{entry.description or 'Sem descricao.'}")
            return
        if panel == "actors":
            actor_id = self._selected_actor_id()
            if actor_id is None:
                detail.update("Selecione um ator.")
                return
            detail.update("\n".join(actor_status_lines(self.session.data, self.catalog, actor_id)))
            return
        lines = diff_summary_lines(self.session.baseline, self.session.data, self.catalog) if self.session.dirty else ["Nenhuma alteracao staged."]
        detail.update("\n".join(lines[:20]))

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
            party = party_actor_ids(self.session.data)
            root.query_one("#action-arms", Button).disabled = (
                self.operation_in_progress or self.actor_selection not in LIMB_REPAIR_CONFIG
            )
            root.query_one("#action-party", Button).disabled = (
                self.operation_in_progress
                or self.actor_selection in party
                or len(party) >= 4
            )
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
        party = set(party_actor_ids(self.session.data))
        ids = actor_ids(self.session.data)
        return sorted(ids, key=lambda actor_id: (actor_id not in party, actor_id))

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
        self.query_one("#slot-meta", Static).update(
            f"file{slot.number}\nBackups: {len(backups)}\nPath: {slot.path}\nMtime: {modified:.0f}"
        )


def main() -> int:
    FearHungerTextualApp().run()
    return 0
