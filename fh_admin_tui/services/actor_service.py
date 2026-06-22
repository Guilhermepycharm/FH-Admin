from __future__ import annotations

from fh_admin_tui.catalog import Catalog, Entry
from fh_admin_tui.domain.character_rules import (
    LIMB_REPAIR_CONFIG,
    actor_display_name,
    actor_ids,
    add_actor_to_party,
    add_skill,
    cure_infections,
    equipped_armor_ids,
    get_actor,
    heal_physical_conditions,
    party_actor_ids,
    restore_supported_limbs,
    revive_actor,
    unequip_armor,
)
from fh_admin_tui.services.results import ActionAvailability, MutationResult

MAX_PARTY_SIZE = 4


class ActorService:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def display_name(self, data: dict, actor_id: int) -> str:
        return actor_display_name(data, self.catalog, actor_id)

    def sorted_actor_ids(self, data: dict) -> list[int]:
        party = set(party_actor_ids(data))
        return sorted(actor_ids(data), key=lambda actor_id: (actor_id not in party, actor_id))

    def limb_restore_action_state(self, actor_id: int) -> ActionAvailability:
        if actor_id in LIMB_REPAIR_CONFIG:
            return ActionAvailability(True)
        return ActionAvailability(False, "Personagem sem reparo de membros mapeado.")

    def party_action_state(self, data: dict, actor_id: int) -> ActionAvailability:
        party = party_actor_ids(data)
        if actor_id in party:
            return ActionAvailability(False, "Personagem ja esta na party.")
        if len(party) >= MAX_PARTY_SIZE:
            return ActionAvailability(False, "A party ja possui quatro membros.")
        return ActionAvailability(True)

    def add_skill(self, data: dict, actor_id: int, skill_id: int) -> MutationResult:
        actor_name = self.display_name(data, actor_id)
        skill = self.catalog.skills.get(skill_id, Entry(skill_id, f"Skill {skill_id}", ""))
        if add_skill(data, actor_id, skill_id):
            return MutationResult(True, f"Skill {skill.name} adicionada a {actor_name}.")
        return MutationResult(False, f"{actor_name} ja conhece {skill.name}.", "warning")

    def revive(self, data: dict, actor_id: int) -> MutationResult:
        actor_name = self.display_name(data, actor_id)
        revive_actor(data, actor_id, clear_switches=(278,) if actor_id == 6 else ())
        return MutationResult(True, f"{actor_name} revivido.")

    def cure_infection(self, data: dict, actor_id: int) -> MutationResult:
        actor_name = self.display_name(data, actor_id)
        removed = cure_infections(data, actor_id)
        return MutationResult(True, f"Infeccoes removidas de {actor_name}: {removed or 'nenhuma'}.")

    def heal_wounds(self, data: dict, actor_id: int) -> MutationResult:
        actor_name = self.display_name(data, actor_id)
        removed = heal_physical_conditions(data, actor_id)
        if not removed:
            return MutationResult(False, f"Nenhum ferimento curavel detectado em {actor_name}.", "warning")
        names = [self.catalog.states[state_id].name for state_id in removed if state_id in self.catalog.states]
        return MutationResult(True, f"Ferimentos curados em {actor_name}: {', '.join(names)}")

    def restore_limbs(self, data: dict, actor_id: int) -> MutationResult:
        actor_name = self.display_name(data, actor_id)
        actor = get_actor(data, actor_id)
        states_before = list(actor["_states"]["@a"])
        restored = restore_supported_limbs(data, actor_id)
        states_changed = states_before != actor["_states"]["@a"]
        if restored or states_changed:
            return MutationResult(True, f"Membros restaurados em {actor_name}: {restored or 'estados corrigidos'}")
        return MutationResult(False, f"Nenhum membro ausente detectado para {actor_name}.", "warning")

    def add_to_party(self, data: dict, actor_id: int) -> MutationResult:
        party = party_actor_ids(data)
        if len(party) >= MAX_PARTY_SIZE and actor_id not in party:
            return MutationResult(False, "A party ja possui quatro membros.", "warning")
        actor_name = self.display_name(data, actor_id)
        if add_actor_to_party(data, actor_id):
            return MutationResult(True, f"{actor_name} adicionado a party.")
        return MutationResult(False, f"{actor_name} ja esta na party.", "warning")

    def equipped_armor_choices(self, data: dict, actor_id: int) -> list[Entry]:
        return [self.catalog.armors.get(armor_id, Entry(armor_id, f"Armor {armor_id}", "")) for armor_id in equipped_armor_ids(data, actor_id)]

    def unequip_armor(self, data: dict, actor_id: int, armor_id: int) -> MutationResult:
        actor_name = self.display_name(data, actor_id)
        armor = self.catalog.armors.get(armor_id, Entry(armor_id, f"Armor {armor_id}", ""))
        if unequip_armor(data, actor_id, armor_id):
            return MutationResult(True, f"{armor.name} removido de {actor_name}.")
        return MutationResult(False, f"{actor_name} nao tem {armor.name} equipada.", "warning")
