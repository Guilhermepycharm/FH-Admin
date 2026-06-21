from __future__ import annotations

from dataclasses import dataclass

from .catalog import Catalog


INFECTION_STATES = (55, 56)
LIMB_CUT_STATES = (3, 14)
PHYSICAL_CONDITION_STATES = (5, 19, 55, 56)
INFECTION_VARIABLES = {
    1: (230, 241),
    2: (231, 242),
    3: (232, 243),
    4: (233, 244),
    5: (234, 245),
    6: (235, 246),
    7: (236, 247),
    8: (237, 248),
    9: (238, 249),
    10: (239, 250),
}
LIMB_REPAIR_CONFIG = {
    1: {"label": "Cahara", "limb_switches": (36, 37, 38, 39)},
    2: {"label": "Girl", "limb_switches": (168, 169, 170, 171)},
    3: {
        "label": "D'arce",
        "arm_switches": (248, 249),
        "limb_switches": (248, 249, 250, 251),
        "character": "knight",
        "face": "Actor1",
        "face_index": 2,
        "battler_missing": "knight1_2",
        "battler_intact": "knight1_1",
    },
    4: {"label": "Enki", "limb_switches": (252, 253, 254, 255)},
    5: {"label": "Ragnvaldr", "limb_switches": (256, 257, 258, 259)},
    6: {
        "label": "Le'garde",
        "arm_switches": (261, 262),
        "limb_switches": (261, 262, 263, 264),
        "character": "captain",
        "face": "Actor2",
        "face_index": 0,
        "battler_missing": "captain1_2",
        "battler_intact": "captain1_1",
    },
    7: {"label": "Moonless", "limb_switches": (270, 271, 272)},
    8: {"label": "Kid Demon", "limb_switches": (381, 382, 383, 384)},
    9: {"label": "Marriage", "limb_switches": (385, 386, 387, 388)},
    10: {"label": "Blood golem", "limb_switches": (376, 377, 378, 379)},
    11: {"label": "Marriage fusion", "limb_switches": (390, 391, 392, 393)},
    16: {"label": "Ghoul 1", "limb_switches": (91, 92, 93, 94)},
    17: {"label": "Ghoul 2", "limb_switches": (155, 156, 157, 158)},
    18: {"label": "Ghoul 3", "limb_switches": (161, 162, 163, 164)},
    19: {"label": "Skeleton 1", "limb_switches": (841, 842, 843, 844)},
    20: {"label": "Skeleton 2", "limb_switches": (845, 846, 847, 848)},
    21: {"label": "Skeleton 3", "limb_switches": (849, 850, 851, 852)},
}

# Backwards-compatible name used by the legacy curses interface.
ARM_REPAIR_CONFIG = LIMB_REPAIR_CONFIG


@dataclass
class OwnedEntry:
    entry_id: int
    quantity: int


def inventory_key(kind: str) -> str:
    return {
        "items": "_items",
        "weapons": "_weapons",
        "armors": "_armors",
    }[kind]


def inventory_map(data: dict, kind: str) -> dict:
    inventory = data["party"][inventory_key(kind)]
    if not isinstance(inventory, dict):
        raise TypeError(f"party.{inventory_key(kind)} is not a dict")
    return inventory


def list_owned_entries(data: dict, kind: str) -> list[OwnedEntry]:
    inventory = inventory_map(data, kind)
    result: list[OwnedEntry] = []
    for key, value in inventory.items():
        if key.isdigit() and isinstance(value, int) and value > 0:
            result.append(OwnedEntry(int(key), value))
    result.sort(key=lambda entry: entry.entry_id)
    return result


def set_quantity(data: dict, kind: str, entry_id: int, quantity: int) -> None:
    inventory = inventory_map(data, kind)
    key = str(entry_id)
    if quantity <= 0:
        inventory.pop(key, None)
    else:
        inventory[key] = quantity


def add_quantity(data: dict, kind: str, entry_id: int, delta: int) -> int:
    inventory = inventory_map(data, kind)
    key = str(entry_id)
    current = inventory.get(key, 0)
    if not isinstance(current, int):
        current = 0
    updated = current + delta
    if updated <= 0:
        inventory.pop(key, None)
        return 0
    inventory[key] = updated
    return updated


def actor_ids(data: dict) -> list[int]:
    actors = data["actors"]["_data"]["@a"]
    if not isinstance(actors, list):
        raise TypeError("actors._data.@a nao e uma lista")
    return [index for index, actor in enumerate(actors) if index > 0 and actor is not None]


def get_actor(data: dict, actor_id: int) -> dict:
    actors = data["actors"]["_data"]["@a"]
    if not isinstance(actor_id, int) or actor_id <= 0 or actor_id >= len(actors):
        raise KeyError(f"actor {actor_id} is out of range")
    actor = actors[actor_id]
    if not isinstance(actor, dict):
        raise KeyError(f"actor {actor_id} is missing")
    return actor


def party_actor_ids(data: dict) -> list[int]:
    party = data["party"]["_actors"]["@a"]
    if not isinstance(party, list):
        raise TypeError("party._actors.@a nao e uma lista")
    return list(party)


def actor_display_name(data: dict, catalog: Catalog, actor_id: int) -> str:
    actor = get_actor(data, actor_id)
    save_name = str(actor.get("_name") or "").strip()
    if save_name:
        return save_name
    catalog_actor = catalog.actors.get(actor_id)
    return catalog_actor.name if catalog_actor is not None else f"Actor {actor_id}"


def add_skill(data: dict, actor_id: int, skill_id: int) -> bool:
    actor = get_actor(data, actor_id)
    skills = actor["_skills"]["@a"]
    if not isinstance(skills, list):
        raise TypeError(f"actor {actor_id} possui lista de skills invalida")
    if skill_id in skills:
        return False
    skills.append(skill_id)
    skills.sort()
    return True


def add_actor_to_party(data: dict, actor_id: int) -> bool:
    party = data["party"]["_actors"]["@a"]
    if actor_id in party:
        return False
    party.append(actor_id)
    return True


def revive_actor(data: dict, actor_id: int, clear_switches: tuple[int, ...] = ()) -> None:
    actor = get_actor(data, actor_id)
    states = actor["_states"]["@a"]
    while 1 in states:
        states.remove(1)
    actor["_stateTurns"].pop("1", None)
    actor["_stateSteps"].pop("1", None)
    actor["_hidden"] = False
    if actor.get("_hp", 0) <= 0:
        base = actor.get("_baseParamCache", {}).get("@a", [1])
        actor["_hp"] = max(1, int(base[0] if base else 1))
    add_actor_to_party(data, actor_id)

    switches = data["switches"]["_data"]["@a"]
    for switch_id in clear_switches:
        if 0 <= switch_id < len(switches):
            switches[switch_id] = None


def cure_infections(data: dict, actor_id: int) -> list[int]:
    actor = get_actor(data, actor_id)
    states = actor["_states"]["@a"]
    removed: list[int] = []
    for state_id in INFECTION_STATES:
        while state_id in states:
            states.remove(state_id)
            removed.append(state_id)
        actor["_stateTurns"].pop(str(state_id), None)
        actor["_stateSteps"].pop(str(state_id), None)

    variables = data["variables"]["_data"]["@a"]
    for variable_id in INFECTION_VARIABLES.get(actor_id, ()):
        if 0 <= variable_id < len(variables):
            variables[variable_id] = 0
    return removed


def heal_physical_conditions(data: dict, actor_id: int) -> list[int]:
    actor = get_actor(data, actor_id)
    states = actor["_states"]["@a"]
    removed: list[int] = []
    for state_id in PHYSICAL_CONDITION_STATES:
        while state_id in states:
            states.remove(state_id)
            removed.append(state_id)
        actor["_stateTurns"].pop(str(state_id), None)
        actor["_stateSteps"].pop(str(state_id), None)

    variables = data["variables"]["_data"]["@a"]
    for variable_id in INFECTION_VARIABLES.get(actor_id, ()):
        if 0 <= variable_id < len(variables):
            variables[variable_id] = 0
    return removed


def restore_supported_limbs(data: dict, actor_id: int) -> list[int]:
    config = LIMB_REPAIR_CONFIG.get(actor_id)
    if config is None:
        return []
    switches = data["switches"]["_data"]["@a"]
    actor = get_actor(data, actor_id)
    restored: list[int] = []

    for switch_id in config["limb_switches"]:
        if 0 <= switch_id < len(switches) and switches[switch_id] is True:
            switches[switch_id] = None
            restored.append(switch_id)

    if restored:
        for state_id in LIMB_CUT_STATES:
            while state_id in actor["_states"]["@a"]:
                actor["_states"]["@a"].remove(state_id)
            actor["_stateTurns"].pop(str(state_id), None)
            actor["_stateSteps"].pop(str(state_id), None)

        arm_switches = set(config.get("arm_switches", ()))
        if arm_switches.intersection(restored):
            actor["_characterName"] = config["character"]
            actor["_characterIndex"] = 0
            actor["_faceName"] = config["face"]
            actor["_faceIndex"] = config["face_index"]
            actor["_battlerName"] = str(actor["_battlerName"]).replace(
                config["battler_missing"], config["battler_intact"], 1
            )
    return restored


def restore_supported_arms(data: dict, actor_id: int) -> list[int]:
    return restore_supported_limbs(data, actor_id)


def equipped_armor_ids(data: dict, actor_id: int) -> list[int]:
    actor = get_actor(data, actor_id)
    equipped: list[int] = []
    for equip in actor["_equips"]["@a"]:
        if not isinstance(equip, dict):
            continue
        if equip.get("_dataClass") == "armor" and int(equip.get("_itemId", 0)) > 0:
            equipped.append(int(equip["_itemId"]))
    return equipped


def unequip_armor(data: dict, actor_id: int, armor_id: int) -> bool:
    actor = get_actor(data, actor_id)
    for equip in actor["_equips"]["@a"]:
        if equip.get("_dataClass") == "armor" and int(equip.get("_itemId", 0)) == armor_id:
            equip["_dataClass"] = ""
            equip["_itemId"] = 0
            inventory = inventory_map(data, "armors")
            key = str(armor_id)
            current = inventory.get(key, 0)
            if not isinstance(current, int):
                current = 0
            inventory[key] = current + 1
            return True
    return False


def actor_status_lines(data: dict, catalog: Catalog, actor_id: int) -> list[str]:
    actor = get_actor(data, actor_id)
    party = party_actor_ids(data)
    state_ids = actor["_states"]["@a"]
    state_names = [
        catalog.states[state_id].name
        for state_id in state_ids
        if state_id in catalog.states and catalog.states[state_id].name
    ]
    skills = actor["_skills"]["@a"]
    lines = [
        f"ID: {actor_id}",
        f"Nome: {actor_display_name(data, catalog, actor_id)}",
        f"Na party: {'sim' if actor_id in party else 'nao'}",
        f"HP: {actor.get('_hp', 0)}",
        f"Hidden: {actor.get('_hidden', False)}",
        f"Skills: {len(skills)}",
        f"States: {', '.join(state_names) if state_names else 'nenhum'}",
    ]
    equipped = equipped_armor_ids(data, actor_id)
    if equipped:
        armor_names = [catalog.armors.get(armor_id, None) for armor_id in equipped]
        rendered = ", ".join(
            entry.name if entry is not None else f"Armor {armor_id}"
            for armor_id, entry in zip(equipped, armor_names)
        )
        lines.append(f"Armors equipadas: {rendered}")
    if actor_id in LIMB_REPAIR_CONFIG:
        switch_ids = LIMB_REPAIR_CONFIG[actor_id]["limb_switches"]
        switches = data["switches"]["_data"]["@a"]
        missing = [
            str(switch_id)
            for switch_id in switch_ids
            if 0 <= switch_id < len(switches) and switches[switch_id] is True
        ]
        lines.append(f"Membros ausentes: {', '.join(missing) if missing else 'nao'}")
    return lines


def validate_data(data: dict) -> list[str]:
    errors: list[str] = []

    try:
        actors = data["actors"]["_data"]["@a"]
        party = data["party"]["_actors"]["@a"]
        if not isinstance(actors, list):
            return ["actors._data.@a nao e uma lista"]
        if not isinstance(party, list):
            return ["party._actors.@a nao e uma lista"]
    except (KeyError, TypeError) as exc:
        return [f"Estrutura ausente no save: {exc}"]

    for kind in ("items", "weapons", "armors"):
        try:
            inventory = inventory_map(data, kind)
        except (KeyError, TypeError) as exc:
            errors.append(f"{kind}: estrutura invalida ({exc})")
            continue
        for key, value in inventory.items():
            if not isinstance(key, str):
                errors.append(f"{kind}: chave nao textual {key!r}")
                continue
            if key.startswith("@"):
                continue
            if not key.isdigit():
                errors.append(f"{kind}: chave nao numerica {key!r}")
            if not isinstance(value, int):
                errors.append(f"{kind}: valor nao inteiro para ID {key}")
            elif value < 0:
                errors.append(f"{kind}: quantidade negativa para ID {key}")

    for actor_id in party:
        if not isinstance(actor_id, int) or actor_id <= 0 or actor_id >= len(actors) or actors[actor_id] is None:
            errors.append(f"party contem ator invalido: {actor_id!r}")

    for actor_id, actor in enumerate(actors):
        if actor_id == 0 or actor is None:
            continue
        if not isinstance(actor, dict):
            errors.append(f"ator {actor_id} possui estrutura invalida")
            continue
        hp = actor.get("_hp", 0)
        if not isinstance(hp, (int, float)):
            errors.append(f"ator {actor_id} com HP nao numerico")
        elif hp < 0:
            errors.append(f"ator {actor_id} com HP negativo")
        try:
            equips = actor["_equips"]["@a"]
        except (KeyError, TypeError):
            errors.append(f"ator {actor_id} sem estrutura de equipamentos")
            continue
        if not isinstance(equips, list):
            errors.append(f"ator {actor_id} com equipamentos invalidos")
            continue
        for equip in equips:
            if not isinstance(equip, dict):
                errors.append(f"ator {actor_id} possui equip invalido")
                continue
            data_class = equip.get("_dataClass")
            try:
                item_id = int(equip.get("_itemId", 0))
            except (TypeError, ValueError):
                errors.append(f"ator {actor_id} possui _itemId invalido")
                continue
            if item_id < 0:
                errors.append(f"ator {actor_id} possui equip com item negativo")
            if data_class not in ("", "weapon", "armor"):
                errors.append(f"ator {actor_id} possui _dataClass invalido: {data_class!r}")

    return errors


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
                f"Ator {actor_display_name(current, catalog, actor_id)}: HP {before_actor.get('_hp')} -> {after_actor.get('_hp')}"
            )

        before_states = set(before_actor["_states"]["@a"])
        after_states = set(after_actor["_states"]["@a"])
        for state_id in sorted(before_states - after_states)[:5]:
            state = catalog.states.get(state_id)
            state_name = state.name if state and state.name else f"state {state_id}"
            lines.append(f"Ator {actor_display_name(current, catalog, actor_id)}: removeu estado {state_name}")
        for state_id in sorted(after_states - before_states)[:5]:
            state = catalog.states.get(state_id)
            state_name = state.name if state and state.name else f"state {state_id}"
            lines.append(f"Ator {actor_display_name(current, catalog, actor_id)}: ganhou estado {state_name}")

        before_skills = set(before_actor["_skills"]["@a"])
        after_skills = set(after_actor["_skills"]["@a"])
        for skill_id in sorted(after_skills - before_skills)[:5]:
            skill = catalog.skills.get(skill_id)
            skill_name = skill.name if skill else f"skill {skill_id}"
            lines.append(f"Ator {actor_display_name(current, catalog, actor_id)}: aprendeu {skill_name}")

        before_equips = equipped_armor_ids(baseline, actor_id)
        after_equips = equipped_armor_ids(current, actor_id)
        if before_equips != after_equips:
            lines.append(
                f"Ator {actor_display_name(current, catalog, actor_id)}: armaduras {before_equips} -> {after_equips}"
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
                    f"Ator {actor_display_name(current, catalog, actor_id)}: restaurou membros {restored_switches}"
                )

    return lines or ["Nenhuma alteracao staged."]
