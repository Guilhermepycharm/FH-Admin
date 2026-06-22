from __future__ import annotations

from fh_admin_tui.catalog import Catalog
from fh_admin_tui.domain.character_rules import (
    LIMB_REPAIR_CONFIG,
    actor_display_name,
    actor_ids,
    equipped_armor_ids,
    get_actor,
    party_actor_ids,
)
from fh_admin_tui.domain.inventory_rules import inventory_map


def diff_summary_lines(baseline: dict, current: dict, catalog: Catalog) -> list[str]:
    lines: list[str] = []

    for kind, label, entries in (
        ("items", "Itens", catalog.items),
        ("weapons", "Armas", catalog.weapons),
        ("armors", "Armaduras", catalog.armors),
    ):
        before = inventory_map(baseline, kind)
        after = inventory_map(current, kind)
        changed_ids = sorted(
            {
                int(key)
                for key in set(before) | set(after)
                if key.isdigit() and before.get(key, 0) != after.get(key, 0)
            }
        )
        for entry_id in changed_ids[:20]:
            old = before.get(str(entry_id), 0)
            new = after.get(str(entry_id), 0)
            entry = entries.get(entry_id)
            name = entry.name if entry else f"ID {entry_id}"
            lines.append(f"{label}: {name} ({entry_id}) {old} -> {new}")
        if len(changed_ids) > 20:
            lines.append(f"{label}: ... mais {len(changed_ids) - 20} alteracoes")

    before_party = party_actor_ids(baseline)
    after_party = party_actor_ids(current)
    added_party = [actor_id for actor_id in after_party if actor_id not in before_party]
    removed_party = [actor_id for actor_id in before_party if actor_id not in after_party]
    for actor_id in added_party:
        lines.append(f"Party: adicionou {actor_display_name(current, catalog, actor_id)} ({actor_id})")
    for actor_id in removed_party:
        lines.append(f"Party: removeu {actor_display_name(baseline, catalog, actor_id)} ({actor_id})")

    for actor_id in actor_ids(current):
        before_actor = get_actor(baseline, actor_id)
        after_actor = get_actor(current, actor_id)
        if before_actor.get("_hp") != after_actor.get("_hp"):
            lines.append(
                f"Personagem {actor_display_name(current, catalog, actor_id)}: "
                f"HP {before_actor.get('_hp')} -> {after_actor.get('_hp')}"
            )

        before_states = set(before_actor["_states"]["@a"])
        after_states = set(after_actor["_states"]["@a"])
        for state_id in sorted(before_states - after_states)[:5]:
            state = catalog.states.get(state_id)
            state_name = state.name if state and state.name else f"state {state_id}"
            lines.append(f"Personagem {actor_display_name(current, catalog, actor_id)}: removeu estado {state_name}")
        for state_id in sorted(after_states - before_states)[:5]:
            state = catalog.states.get(state_id)
            state_name = state.name if state and state.name else f"state {state_id}"
            lines.append(f"Personagem {actor_display_name(current, catalog, actor_id)}: ganhou estado {state_name}")

        before_skills = set(before_actor["_skills"]["@a"])
        after_skills = set(after_actor["_skills"]["@a"])
        for skill_id in sorted(after_skills - before_skills)[:5]:
            skill = catalog.skills.get(skill_id)
            skill_name = skill.name if skill else f"skill {skill_id}"
            lines.append(f"Personagem {actor_display_name(current, catalog, actor_id)}: aprendeu {skill_name}")

        before_equips = equipped_armor_ids(baseline, actor_id)
        after_equips = equipped_armor_ids(current, actor_id)
        if before_equips != after_equips:
            lines.append(
                f"Personagem {actor_display_name(current, catalog, actor_id)}: "
                f"armaduras {before_equips} -> {after_equips}"
            )

        limb_config = LIMB_REPAIR_CONFIG.get(actor_id)
        if limb_config is not None:
            before_switches = baseline["switches"]["_data"]["@a"]
            after_switches = current["switches"]["_data"]["@a"]
            restored_switches = [
                switch_id
                for switch_id in limb_config["limb_switches"]
                if switch_id < len(before_switches)
                and switch_id < len(after_switches)
                and before_switches[switch_id] is True
                and after_switches[switch_id] is not True
            ]
            if restored_switches:
                lines.append(
                    f"Personagem {actor_display_name(current, catalog, actor_id)}: "
                    f"restaurou membros {restored_switches}"
                )

    return lines or ["Nenhuma alteracao staged."]
