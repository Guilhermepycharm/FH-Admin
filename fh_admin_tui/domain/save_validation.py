from __future__ import annotations

from fh_admin_tui.domain.inventory_rules import inventory_map


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
            errors.append(f"party contem personagem invalido: {actor_id!r}")

    for actor_id, actor in enumerate(actors):
        if actor_id == 0 or actor is None:
            continue
        if not isinstance(actor, dict):
            errors.append(f"personagem {actor_id} possui estrutura invalida")
            continue
        hp = actor.get("_hp", 0)
        if not isinstance(hp, (int, float)):
            errors.append(f"personagem {actor_id} com HP nao numerico")
        elif hp < 0:
            errors.append(f"personagem {actor_id} com HP negativo")
        try:
            equips = actor["_equips"]["@a"]
        except (KeyError, TypeError):
            errors.append(f"personagem {actor_id} sem estrutura de equipamentos")
            continue
        if not isinstance(equips, list):
            errors.append(f"personagem {actor_id} com equipamentos invalidos")
            continue
        for equip in equips:
            if not isinstance(equip, dict):
                errors.append(f"personagem {actor_id} possui equip invalido")
                continue
            data_class = equip.get("_dataClass")
            try:
                item_id = int(equip.get("_itemId", 0))
            except (TypeError, ValueError):
                errors.append(f"personagem {actor_id} possui _itemId invalido")
                continue
            if item_id < 0:
                errors.append(f"personagem {actor_id} possui equip com item negativo")
            if data_class not in ("", "weapon", "armor"):
                errors.append(f"personagem {actor_id} possui _dataClass invalido: {data_class!r}")

    return errors
