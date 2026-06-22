from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static


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
