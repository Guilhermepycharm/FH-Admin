from __future__ import annotations

from fh_admin_tui.catalog import Catalog
from fh_admin_tui.domain.inventory_rules import inventory_map


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


def actor_ids(data: dict) -> list[int]:
    actors = data["actors"]["_data"]["@a"]
    if not isinstance(actors, list):
        raise TypeError("actors._data.@a nao e uma lista")
    return [index for index, actor in enumerate(actors) if index > 0 and actor is not None]


def get_actor(data: dict, actor_id: int) -> dict:
    actors = data["actors"]["_data"]["@a"]
    if not isinstance(actor_id, int) or actor_id <= 0 or actor_id >= len(actors):
        raise KeyError(f"personagem {actor_id} esta fora do intervalo")
    actor = actors[actor_id]
    if not isinstance(actor, dict):
        raise KeyError(f"personagem {actor_id} ausente")
    return actor


def party_actor_ids(data: dict) -> list[int]:
    party = data["party"]["_actors"]["@a"]
    if not isinstance(party, list):
        raise TypeError("party._actors.@a nao e uma lista")
    return list(party)


def actor_display_name(data: dict, catalog: Catalog, actor_id: int) -> str:
    try:
        actor = get_actor(data, actor_id)
    except KeyError:
        catalog_actor = catalog.actors.get(actor_id)
        return catalog_actor.name if catalog_actor is not None else f"Personagem {actor_id}"
    save_name = str(actor.get("_name") or "").strip()
    if save_name:
        return save_name
    catalog_actor = catalog.actors.get(actor_id)
    return catalog_actor.name if catalog_actor is not None else f"Personagem {actor_id}"


def add_skill(data: dict, actor_id: int, skill_id: int) -> bool:
    actor = get_actor(data, actor_id)
    skills = actor["_skills"]["@a"]
    if not isinstance(skills, list):
        raise TypeError(f"personagem {actor_id} possui lista de skills invalida")
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
