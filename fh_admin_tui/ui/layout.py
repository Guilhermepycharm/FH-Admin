from __future__ import annotations

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label, ListView, Static, TabbedContent, TabPane

APP_CSS = """
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

APP_BINDINGS = [
    Binding("ctrl+q", "request_quit", "Sair"),
    Binding("f5", "reload_slots", "Recarregar slots"),
    Binding("ctrl+b", "backup_current", "Backup"),
    Binding("ctrl+r", "reload_session", "Recarregar slot"),
    Binding("ctrl+s", "apply_changes", "Apply"),
    Binding("?", "show_help", "Ajuda"),
]

PANEL_TITLES = {
    "summary": "Resumo",
    "items": "Itens",
    "weapons": "Armas",
    "armors": "Armaduras",
    "actors": "Personagens",
}


def compose_main_layout():
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
                with TabPane("Personagens", id="actors"):
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
                yield Button("Reviver personagem", id="action-revive")
                yield Button("Curar infeccao", id="action-infection")
                yield Button("Curar ferimentos", id="action-wounds")
                yield Button("Restaurar membros", id="action-arms")
                yield Button("Adicionar a party atual", id="action-party")
                yield Button("Desequipar armadura", id="action-unequip")
                yield Button("Aplicar alteracoes", id="action-apply", variant="success")
    yield Footer()


def setup_editor_tables(app) -> None:
    for table_id in ("items-table", "weapons-table", "armors-table"):
        table = app.query_one(f"#{table_id}", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Nome", "Qtd", "Descricao")
    actors = app.query_one("#actors-table", DataTable)
    actors.cursor_type = "row"
    actors.add_columns("ID", "Nome", "Party", "HP", "States")
