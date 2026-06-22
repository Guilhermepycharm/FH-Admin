"""Legacy curses interface kept outside the primary Textual path.

The supported application entrypoint is fh_admin_tui.textual_app. This module is
kept for compatibility while save/domain behavior is shared through save_ops and
mutations.
"""

from __future__ import annotations

import curses
import textwrap
import traceback
from dataclasses import dataclass

from ..catalog import Catalog, Entry
from ..diagnostics import LOG_PATH, configure_logging, get_logger
from ..mutations import (
    ARM_REPAIR_CONFIG,
    actor_display_name,
    actor_ids,
    actor_status_lines,
    add_actor_to_party,
    add_quantity,
    add_skill,
    cure_infections,
    diff_summary_lines,
    equipped_armor_ids,
    list_owned_entries,
    party_actor_ids,
    restore_supported_arms,
    revive_actor,
    set_quantity,
    unequip_armor,
    validate_data,
)
from ..save_ops import SaveRepository, SaveSession, SaveSlot


PANEL_NAMES = {
    "summary": "Resumo",
    "items": "Itens",
    "weapons": "Armas",
    "armors": "Armaduras",
    "actors": "Personagens",
}


@dataclass
class SearchChoice:
    entry_id: int
    label: str
    description: str


class FearHungerAdminTUI:
    def __init__(self) -> None:
        self.repo = SaveRepository()
        self.catalog = Catalog.load(self.repo.data_dir)
        self.slots: list[SaveSlot] = self.repo.list_slots()
        self.slot_index = 0
        self.session: SaveSession | None = None
        self.panel = "summary"
        self.inventory_index = {"items": 0, "weapons": 0, "armors": 0}
        self.actor_index = 0
        self.status = "Pronto."
        self.running = True

    def run(self, stdscr) -> None:
        self._set_cursor(0)
        stdscr.keypad(True)
        while self.running:
            stdscr.erase()
            if self.session is None:
                self.draw_slots(stdscr)
                key = stdscr.getch()
                self.handle_slots_key(stdscr, key)
            else:
                self.draw_session(stdscr)
                key = stdscr.getch()
                self.handle_session_key(stdscr, key)

    def draw_slots(self, stdscr) -> None:
        height, width = stdscr.getmaxyx()
        self._draw_header(stdscr, "Fear & Hunger Admin TUI", width)
        stdscr.addstr(2, 2, "Slots encontrados")
        if not self.slots:
            stdscr.addstr(4, 4, "Nenhum save encontrado em www/save")
        for row, slot in enumerate(self.slots[: max(0, height - 8)]):
            y = 4 + row
            selected = row == self.slot_index
            marker = ">" if selected else " "
            style = curses.A_REVERSE if selected else curses.A_NORMAL
            label = f"{marker} file{slot.number}.rpgsave"
            stdscr.addstr(y, 4, self._trim(label, width - 8), style)
        help_text = "Enter abrir  b backup  t restaurar backup  r recarregar  q sair"
        self._draw_footer(stdscr, help_text, width)
        self._draw_status(stdscr, width)

    def draw_session(self, stdscr) -> None:
        assert self.session is not None
        height, width = stdscr.getmaxyx()
        dirty = " *ALTERADO*" if self.session.dirty else ""
        title = f"Slot {self.session.slot.number}{dirty}"
        self._draw_header(stdscr, title, width)
        nav = "1 Resumo  2 Itens  3 Armas  4 Armaduras  5 Personagens"
        stdscr.addstr(2, 2, self._trim(nav, width - 4))

        if self.panel == "summary":
            self.draw_summary_panel(stdscr)
            help_text = "1-5 trocar painel  p revisar/apply  B backup  T restore  R recarregar  q voltar"
        elif self.panel in {"items", "weapons", "armors"}:
            self.draw_inventory_panel(stdscr, self.panel)
            help_text = "n novo  e set  + soma  - subtrai  d remove  p revisar  q voltar"
        else:
            self.draw_actor_panel(stdscr)
            help_text = "s skill  v revive  i cura infeccao  m restaura braco  o party  u desequipar  p revisar"

        self._draw_footer(stdscr, help_text, width)
        self._draw_status(stdscr, width)

    def draw_summary_panel(self, stdscr) -> None:
        assert self.session is not None
        height, width = stdscr.getmaxyx()
        party = party_actor_ids(self.session.data)
        stdscr.addstr(4, 2, "Party atual")
        y = 5
        for actor_id in party[: max(0, height - 12)]:
            line = f"- {actor_display_name(self.session.data, self.catalog, actor_id)} (ID {actor_id})"
            stdscr.addstr(y, 4, self._trim(line, width - 8))
            y += 1

        counts = {
            "Itens": len(list_owned_entries(self.session.data, "items")),
            "Armas": len(list_owned_entries(self.session.data, "weapons")),
            "Armaduras": len(list_owned_entries(self.session.data, "armors")),
        }
        y += 1
        for label, amount in counts.items():
            stdscr.addstr(y, 4, f"{label}: {amount}")
            y += 1

        y += 1
        stdscr.addstr(y, 2, "Personagens com reparo especial suportado")
        y += 1
        for actor_id, config in ARM_REPAIR_CONFIG.items():
            actor_name = actor_display_name(self.session.data, self.catalog, actor_id)
            line = f"- {actor_name} (ID {actor_id})"
            stdscr.addstr(y, 4, self._trim(line, width - 8))
            y += 1

    def draw_inventory_panel(self, stdscr, kind: str) -> None:
        assert self.session is not None
        height, width = stdscr.getmaxyx()
        owned = list_owned_entries(self.session.data, kind)
        entries = self.catalog.entries_for_kind(kind)
        index = min(self.inventory_index[kind], max(len(owned) - 1, 0))
        self.inventory_index[kind] = index
        title = PANEL_NAMES[kind]
        stdscr.addstr(4, 2, title)
        left_width = max(30, width // 2)

        if not owned:
            stdscr.addstr(6, 4, "Nenhuma entrada. Use 'n' para adicionar.")
            return

        visible_rows = max(5, height - 10)
        start = max(0, index - visible_rows // 2)
        for row, owned_entry in enumerate(owned[start : start + visible_rows]):
            y = 6 + row
            selected = start + row == index
            style = curses.A_REVERSE if selected else curses.A_NORMAL
            entry = entries.get(owned_entry.entry_id)
            name = entry.name if entry else f"ID {owned_entry.entry_id}"
            text = f"{owned_entry.entry_id:>3}  x{owned_entry.quantity:<4} {name}"
            stdscr.addstr(y, 4, self._trim(text, left_width - 6), style)

        selected_entry = owned[index]
        details = entries.get(selected_entry.entry_id)
        detail_x = left_width + 2
        stdscr.addstr(4, detail_x, "Detalhes")
        if details:
            lines = [
                f"ID: {details.entry_id}",
                f"Nome: {details.name}",
                f"Qtd: {selected_entry.quantity}",
            ]
            for line_row, line in enumerate(lines, start=6):
                stdscr.addstr(line_row, detail_x, self._trim(line, width - detail_x - 2))
            desc_lines = textwrap.wrap(details.description or "Sem descricao.", width=max(20, width - detail_x - 2))
            for offset, line in enumerate(desc_lines[: max(3, height - 14)], start=10):
                stdscr.addstr(offset, detail_x, self._trim(line, width - detail_x - 2))

    def draw_actor_panel(self, stdscr) -> None:
        assert self.session is not None
        height, width = stdscr.getmaxyx()
        actor_list = self._actor_list()
        self.actor_index = min(self.actor_index, max(len(actor_list) - 1, 0))
        stdscr.addstr(4, 2, "Personagens")
        left_width = max(30, width // 2)

        visible_rows = max(5, height - 10)
        start = max(0, self.actor_index - visible_rows // 2)
        for row, actor_id in enumerate(actor_list[start : start + visible_rows]):
            y = 6 + row
            selected = start + row == self.actor_index
            style = curses.A_REVERSE if selected else curses.A_NORMAL
            party_mark = "*" if actor_id in party_actor_ids(self.session.data) else " "
            name = actor_display_name(self.session.data, self.catalog, actor_id)
            text = f"{party_mark} {actor_id:>2} {name}"
            stdscr.addstr(y, 4, self._trim(text, left_width - 6), style)

        if not actor_list:
            stdscr.addstr(6, 4, "Nenhum personagem no save.")
            return

        actor_id = actor_list[self.actor_index]
        detail_x = left_width + 2
        stdscr.addstr(4, detail_x, "Detalhes")
        lines = actor_status_lines(self.session.data, self.catalog, actor_id)
        for line_row, line in enumerate(lines, start=6):
            if line_row >= height - 3:
                break
            stdscr.addstr(line_row, detail_x, self._trim(line, width - detail_x - 2))

    def handle_slots_key(self, stdscr, key: int) -> None:
        if key in (curses.KEY_DOWN, ord("j")) and self.slot_index < len(self.slots) - 1:
            self.slot_index += 1
        elif key in (curses.KEY_UP, ord("k")) and self.slot_index > 0:
            self.slot_index -= 1
        elif key in (10, 13, curses.KEY_ENTER):
            if not self.slots:
                self.status = "Nenhum slot para abrir."
                return
            self.session = self.repo.open_session(self.slots[self.slot_index])
            self.panel = "summary"
            self.status = f"Slot {self.session.slot.number} aberto."
        elif key == ord("b"):
            if not self.slots:
                self.status = "Nenhum slot para backup."
                return
            backup = self.repo.create_backup(self.slots[self.slot_index])
            self.status = f"Backup criado: {backup.name}"
        elif key == ord("t"):
            if not self.slots:
                self.status = "Nenhum slot para restaurar."
                return
            self.restore_backup_flow(stdscr, self.slots[self.slot_index])
        elif key == ord("r"):
            self.slots = self.repo.list_slots()
            self.slot_index = min(self.slot_index, max(len(self.slots) - 1, 0))
            self.status = "Lista de slots recarregada."
        elif key == ord("q"):
            self.running = False

    def handle_session_key(self, stdscr, key: int) -> None:
        assert self.session is not None
        if key in map(ord, "12345"):
            self.panel = {
                ord("1"): "summary",
                ord("2"): "items",
                ord("3"): "weapons",
                ord("4"): "armors",
                ord("5"): "actors",
            }[key]
            return
        if key == ord("p"):
            if not self.session.dirty:
                self.status = "Nao ha alteracoes staged."
                return
            if not self.review_and_confirm_apply(stdscr):
                self.status = "Apply cancelado."
                return
            try:
                backup = self.session.apply()
            except ValueError as exc:
                self.status = str(exc)
                return
            self.status = f"Alteracoes aplicadas. Backup: {backup.name}"
            return
        if key == ord("B"):
            backup = self.repo.create_backup(self.session.slot)
            self.status = f"Backup criado: {backup.name}"
            return
        if key == ord("T"):
            self.restore_backup_flow(stdscr, self.session.slot)
            if self.session is not None:
                self.session.reload()
            return
        if key == ord("R"):
            if self.session.dirty and not self.confirm(stdscr, "Descartar alteracoes staged e recarregar?"):
                self.status = "Recarregamento cancelado."
                return
            self.session.reload()
            self.status = "Sessao recarregada do save original."
            return
        if key == ord("q"):
            if self.session.dirty and not self.confirm(stdscr, "Sair do slot e perder alteracoes staged?"):
                self.status = "Saida cancelada."
                return
            self.session.close()
            self.session = None
            self.status = "Voltou para a lista de slots."
            return

        if self.panel in {"items", "weapons", "armors"}:
            self.handle_inventory_key(stdscr, self.panel, key)
        elif self.panel == "actors":
            self.handle_actor_key(stdscr, key)

    def handle_inventory_key(self, stdscr, kind: str, key: int) -> None:
        assert self.session is not None
        owned = list_owned_entries(self.session.data, kind)
        if key in (curses.KEY_DOWN, ord("j")) and self.inventory_index[kind] < len(owned) - 1:
            self.inventory_index[kind] += 1
            return
        if key in (curses.KEY_UP, ord("k")) and self.inventory_index[kind] > 0:
            self.inventory_index[kind] -= 1
            return
        if key == ord("n"):
            query = self.prompt(stdscr, f"Buscar em {PANEL_NAMES[kind]} por nome ou ID")
            if query is None:
                return
            chosen = self.choose_catalog_entry(stdscr, kind, query)
            if chosen is None:
                self.status = "Busca cancelada."
                return
            quantity = self.prompt_int(stdscr, "Quantidade inicial", default=1)
            if quantity is None:
                return
            add_quantity(self.session.data, kind, chosen.entry_id, quantity)
            self.session.mark_dirty()
            self.status = f"{chosen.name} ajustado em {quantity}."
            return
        if not owned:
            return

        selected = owned[self.inventory_index[kind]]
        entry = self.catalog.entries_for_kind(kind).get(selected.entry_id)
        label = entry.name if entry else f"ID {selected.entry_id}"
        if key == ord("e"):
            quantity = self.prompt_int(stdscr, f"Quantidade exata para {label}", default=selected.quantity)
            if quantity is None:
                return
            set_quantity(self.session.data, kind, selected.entry_id, quantity)
            self.session.mark_dirty()
            self.status = f"{label} agora esta em {quantity}."
        elif key == ord("+"):
            quantity = self.prompt_int(stdscr, f"Somar quantidade em {label}", default=1)
            if quantity is None:
                return
            updated = add_quantity(self.session.data, kind, selected.entry_id, quantity)
            self.session.mark_dirty()
            self.status = f"{label} agora esta em {updated}."
        elif key == ord("-"):
            quantity = self.prompt_int(stdscr, f"Subtrair quantidade de {label}", default=1)
            if quantity is None:
                return
            updated = add_quantity(self.session.data, kind, selected.entry_id, -quantity)
            self.session.mark_dirty()
            self.status = f"{label} agora esta em {updated}."
        elif key == ord("d"):
            set_quantity(self.session.data, kind, selected.entry_id, 0)
            self.session.mark_dirty()
            self.inventory_index[kind] = max(0, self.inventory_index[kind] - 1)
            self.status = f"{label} removido."

    def handle_actor_key(self, stdscr, key: int) -> None:
        assert self.session is not None
        actor_list = self._actor_list()
        if key in (curses.KEY_DOWN, ord("j")) and self.actor_index < len(actor_list) - 1:
            self.actor_index += 1
            return
        if key in (curses.KEY_UP, ord("k")) and self.actor_index > 0:
            self.actor_index -= 1
            return
        if not actor_list:
            return

        actor_id = actor_list[self.actor_index]
        actor_name = actor_display_name(self.session.data, self.catalog, actor_id)

        if key == ord("s"):
            query = self.prompt(stdscr, f"Buscar skill para {actor_name}")
            if query is None:
                return
            chosen = self.choose_catalog_entry(stdscr, "skills", query)
            if chosen is None:
                self.status = "Busca cancelada."
                return
            changed = add_skill(self.session.data, actor_id, chosen.entry_id)
            if changed:
                self.session.mark_dirty()
                self.status = f"Skill {chosen.name} adicionada a {actor_name}."
            else:
                self.status = f"{actor_name} ja conhece {chosen.name}."
        elif key == ord("v"):
            clear_switches = (278,) if actor_id == 6 else ()
            revive_actor(self.session.data, actor_id, clear_switches=clear_switches)
            self.session.mark_dirty()
            self.status = f"{actor_name} revivido."
        elif key == ord("i"):
            removed = cure_infections(self.session.data, actor_id)
            self.session.mark_dirty()
            self.status = f"Infeccoes removidas de {actor_name}: {removed or 'nenhuma'}."
        elif key == ord("m"):
            restored = restore_supported_arms(self.session.data, actor_id)
            if restored:
                self.session.mark_dirty()
                self.status = f"Bracos restaurados em {actor_name}: {restored}"
            else:
                self.status = f"Nenhum reparo de braco aplicavel para {actor_name}."
        elif key == ord("o"):
            changed = add_actor_to_party(self.session.data, actor_id)
            if changed:
                self.session.mark_dirty()
                self.status = f"{actor_name} adicionado a party."
            else:
                self.status = f"{actor_name} ja esta na party."
        elif key == ord("u"):
            equipped = equipped_armor_ids(self.session.data, actor_id)
            if not equipped:
                self.status = f"{actor_name} nao tem armor/acessorio equipado."
                return
            choices = [
                SearchChoice(
                    armor_id,
                    self.catalog.armors.get(armor_id, Entry(armor_id, f"Armor {armor_id}", "")).name,
                    "",
                )
                for armor_id in equipped
            ]
            chosen = self.choose_from_list(stdscr, f"Remover armor de {actor_name}", choices)
            if chosen is None:
                self.status = "Remocao cancelada."
                return
            removed = unequip_armor(self.session.data, actor_id, chosen.entry_id)
            if removed:
                self.session.mark_dirty()
                self.status = f"{chosen.label} removido de {actor_name}."
            else:
                self.status = f"Nao foi possivel remover {chosen.label}."

    def choose_catalog_entry(self, stdscr, kind: str, query: str) -> Entry | None:
        matches = self.catalog.search(kind, query)
        if not matches:
            self.status = "Nenhum resultado."
            return None
        choices = [SearchChoice(entry.entry_id, entry.name, entry.description) for entry in matches]
        chosen = self.choose_from_list(stdscr, f"Escolha em {PANEL_NAMES.get(kind, kind)}", choices)
        if chosen is None:
            return None
        return self.catalog.entries_for_kind(kind)[chosen.entry_id]

    def review_and_confirm_apply(self, stdscr) -> bool:
        assert self.session is not None
        lines = diff_summary_lines(self.session.baseline, self.session.data, self.catalog)
        validation_errors = validate_data(self.session.data)
        scroll = 0

        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            self._draw_header(stdscr, "Revisao antes do apply", width)
            body = lines[:]
            if validation_errors:
                body.append("")
                body.append("Erros de validacao:")
                body.extend(f"- {error}" for error in validation_errors[:10])
            visible_rows = max(5, height - 6)
            max_scroll = max(0, len(body) - visible_rows)
            scroll = min(scroll, max_scroll)
            for row, line in enumerate(body[scroll : scroll + visible_rows]):
                self._safe_addstr(stdscr, 2 + row, 2, self._trim(line, width - 4))
            footer = "P ou Enter confirma  Esc cancela  j/k rola"
            if validation_errors:
                footer = "Validacao falhou. Esc para voltar."
            self._draw_footer(stdscr, footer, width)
            key = stdscr.getch()
            if key in (curses.KEY_DOWN, ord("j")) and scroll < max_scroll:
                scroll += 1
            elif key in (curses.KEY_UP, ord("k")) and scroll > 0:
                scroll -= 1
            elif not validation_errors and key in (ord("P"), 10, 13, curses.KEY_ENTER):
                return True
            elif key in (27, ord("q")):
                return False

    def restore_backup_flow(self, stdscr, slot: SaveSlot) -> None:
        backups = self.repo.list_backups(slot)
        if not backups:
            self.status = f"Nenhum backup encontrado para file{slot.number}."
            return
        choices = [SearchChoice(index, path.name, str(path)) for index, path in enumerate(backups)]
        chosen = self.choose_from_list(stdscr, f"Restaurar backup de file{slot.number}", choices)
        if chosen is None:
            self.status = "Restauracao cancelada."
            return
        backup_path = backups[chosen.entry_id]
        if not self.confirm(stdscr, f"Restaurar {backup_path.name} em file{slot.number}?"):
            self.status = "Restauracao cancelada."
            return
        safety = self.repo.restore_backup(slot, backup_path)
        self.status = f"Backup restaurado. Save anterior salvo em {safety.name}."

    def choose_from_list(self, stdscr, title: str, choices: list[SearchChoice]) -> SearchChoice | None:
        index = 0
        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            self._draw_header(stdscr, title, width)
            visible_rows = max(5, height - 8)
            start = max(0, index - visible_rows // 2)
            for row, choice in enumerate(choices[start : start + visible_rows]):
                y = 3 + row
                selected = start + row == index
                style = curses.A_REVERSE if selected else curses.A_NORMAL
                label = f"{choice.entry_id:>3} {choice.label}"
                stdscr.addstr(y, 2, self._trim(label, width - 4), style)
            description = choices[index].description or "Sem descricao."
            wrapped = textwrap.wrap(description, width=max(20, width - 4))
            desc_y = min(height - 4, 5 + visible_rows)
            for offset, line in enumerate(wrapped[: max(1, height - desc_y - 2)]):
                stdscr.addstr(desc_y + offset, 2, self._trim(line, width - 4))
            self._draw_footer(stdscr, "Enter escolher  Esc cancelar", width)
            key = stdscr.getch()
            if key in (curses.KEY_DOWN, ord("j")) and index < len(choices) - 1:
                index += 1
            elif key in (curses.KEY_UP, ord("k")) and index > 0:
                index -= 1
            elif key in (10, 13, curses.KEY_ENTER):
                return choices[index]
            elif key in (27, ord("q")):
                return None

    def prompt(self, stdscr, label: str, default: str = "") -> str | None:
        height, width = stdscr.getmaxyx()
        self._set_cursor(1)
        curses.echo()
        try:
            stdscr.move(height - 2, 0)
            stdscr.clrtoeol()
            prompt = f"{label}: "
            stdscr.addstr(height - 2, 0, self._trim(prompt, width - 1))
            stdscr.refresh()
            raw = stdscr.getstr(height - 2, min(len(prompt), width - 1), max(1, width - len(prompt) - 1))
            if raw is None:
                return None
            value = raw.decode("utf-8", errors="ignore").strip()
            if not value:
                return default if default else None
            return value
        finally:
            curses.noecho()
            self._set_cursor(0)

    def prompt_int(self, stdscr, label: str, default: int = 0) -> int | None:
        value = self.prompt(stdscr, f"{label} [{default}]", str(default))
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            self.status = "Numero invalido."
            return None

    def confirm(self, stdscr, question: str) -> bool:
        height, width = stdscr.getmaxyx()
        self._safe_addstr(stdscr, height - 2, 0, self._trim(f"{question} [y/N]", width))
        while True:
            key = stdscr.getch()
            if key in (ord("y"), ord("Y")):
                return True
            if key in (ord("n"), ord("N"), 27, 10, 13):
                return False

    def _actor_list(self) -> list[int]:
        party = set(party_actor_ids(self.session.data)) if self.session is not None else set()
        ids = actor_ids(self.session.data) if self.session is not None else []
        return sorted(ids, key=lambda actor_id: (actor_id not in party, actor_id))

    def _draw_header(self, stdscr, title: str, width: int) -> None:
        self._safe_addstr(stdscr, 0, 0, self._trim(title, width), curses.A_REVERSE)

    def _draw_footer(self, stdscr, text: str, width: int) -> None:
        height, _ = stdscr.getmaxyx()
        self._safe_addstr(stdscr, height - 1, 0, self._trim(text, width), curses.A_REVERSE)

    def _draw_status(self, stdscr, width: int) -> None:
        height, _ = stdscr.getmaxyx()
        self._safe_addstr(stdscr, height - 2, 0, self._trim(self.status, width))

    @staticmethod
    def _trim(text: str, width: int) -> str:
        if width <= 0:
            return ""
        if len(text) <= width:
            return text.ljust(width)
        return text[: max(0, width - 1)] + "…"

    @staticmethod
    def _set_cursor(visible: int) -> None:
        try:
            curses.curs_set(visible)
        except curses.error:
            pass

    @staticmethod
    def _safe_addstr(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass


def main() -> int:
    configure_logging()
    logger = get_logger("legacy_tui")
    try:
        curses.wrapper(lambda stdscr: FearHungerAdminTUI().run(stdscr))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        logger.exception("Falha fatal no TUI legado")
        traceback.print_exc()
        print(f"Detalhes registrados em {LOG_PATH}")
        return 1
