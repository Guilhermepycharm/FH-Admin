from __future__ import annotations

from pathlib import Path

from fh_admin_tui.catalog import Catalog, Entry
from fh_admin_tui.domain.character_rules import actor_display_name, actor_status_lines, party_actor_ids
from fh_admin_tui.domain.inventory_rules import list_owned_entries
from fh_admin_tui.domain.save_validation import validate_data
from fh_admin_tui.save_ops import SaveSession, SaveSlot


def summary_text(session: SaveSession | None, catalog: Catalog) -> str:
    if session is None:
        return "Selecione um slot para começar."
    slot = session.slot
    lines = [f"Slot: file{slot.number}.rpgsave", f"Alterado: {'sim' if session.dirty else 'nao'}", ""]
    lines.append("Party atual:")
    for actor_id in party_actor_ids(session.data):
        lines.append(f"- {actor_display_name(session.data, catalog, actor_id)} (ID {actor_id})")
    lines.extend(
        [
            "",
            f"Itens: {len(list_owned_entries(session.data, 'items'))}",
            f"Armas: {len(list_owned_entries(session.data, 'weapons'))}",
            f"Armaduras: {len(list_owned_entries(session.data, 'armors'))}",
        ]
    )
    errors = validate_data(session.data)
    lines.append("")
    lines.append("Validacao: OK" if not errors else "Validacao: com erros")
    if errors:
        lines.extend(f"- {error}" for error in errors[:8])
    return "\n".join(lines)


def inventory_rows(session: SaveSession | None, catalog: Catalog, kind: str) -> list[tuple[str, str, str, str]]:
    if session is None:
        return []
    rows: list[tuple[str, str, str, str]] = []
    for owned in list_owned_entries(session.data, kind):
        entry = catalog.entries_for_kind(kind).get(owned.entry_id, Entry(owned.entry_id, f"ID {owned.entry_id}", ""))
        rows.append((str(owned.entry_id), entry.name, str(owned.quantity), entry.description[:64]))
    return rows


def actor_rows(session: SaveSession | None, catalog: Catalog, actor_ids: list[int]) -> list[tuple[str, str, str, str, str]]:
    if session is None:
        return []
    rows: list[tuple[str, str, str, str, str]] = []
    party = party_actor_ids(session.data)
    for actor_id in actor_ids:
        actor = session.data["actors"]["_data"]["@a"][actor_id]
        state_names = [
            catalog.states[state_id].name
            for state_id in actor["_states"]["@a"]
            if state_id in catalog.states and catalog.states[state_id].name
        ]
        rows.append(
            (
                str(actor_id),
                actor_display_name(session.data, catalog, actor_id),
                "sim" if actor_id in party else "nao",
                str(actor.get("_hp", 0)),
                ", ".join(state_names[:3]) or "nenhum",
            )
        )
    return rows


def inventory_detail_text(session: SaveSession, catalog: Catalog, kind: str, entry_id: int | None) -> str:
    if entry_id is None:
        return "Selecione uma entrada."
    entry = catalog.entries_for_kind(kind).get(entry_id, Entry(entry_id, f"ID {entry_id}", ""))
    quantity = next((owned.quantity for owned in list_owned_entries(session.data, kind) if owned.entry_id == entry_id), 0)
    return f"ID: {entry.entry_id}\nNome: {entry.name}\nQtd: {quantity}\n\n{entry.description or 'Sem descricao.'}"


def actor_detail_text(session: SaveSession, catalog: Catalog, actor_id: int | None) -> str:
    if actor_id is None:
        return "Selecione um personagem."
    return "\n".join(actor_status_lines(session.data, catalog, actor_id))


def staged_detail_text(session: SaveSession, catalog: Catalog) -> str:
    lines = diff_summary_lines(session.baseline, session.data, catalog) if session.dirty else ["Nenhuma alteracao staged."]
    return "\n".join(lines[:20])


def slot_meta_text(slot: SaveSlot, backups: list[Path], modified: float) -> str:
    return f"file{slot.number}\nBackups: {len(backups)}\nPath: {slot.path}\nMtime: {modified:.0f}"
