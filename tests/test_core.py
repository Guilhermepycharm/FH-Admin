from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fh_admin_tui.catalog import Catalog
from fh_admin_tui.save_ops import SaveOperationError
from fh_admin_tui.mutations import (
    actor_display_name,
    add_actor_to_party,
    heal_physical_conditions,
    restore_supported_limbs,
    validate_data,
)

from tests.fixtures.helpers import build_fake_repository, build_test_catalog


class CoreTests(unittest.TestCase):
    def test_repairs_limbs_wounds_and_party_membership(self) -> None:
        actor = {
            "_name": "Cahara",
            "_states": {"@a": [3, 14, 5, 19, 55, 56]},
            "_stateTurns": {str(state_id): 3 for state_id in (3, 5, 14, 19, 55, 56)},
            "_stateSteps": {str(state_id): 3 for state_id in (3, 5, 14, 19, 55, 56)},
        }
        switches = [None] * 900
        switches[36] = True
        switches[39] = True
        data = {
            "actors": {"_data": {"@a": [None, actor]}},
            "party": {"_actors": {"@a": []}},
            "switches": {"_data": {"@a": switches}},
            "variables": {"_data": {"@a": [0] * 300}},
        }

        self.assertEqual(restore_supported_limbs(data, 1), [36, 39])
        self.assertNotIn(3, actor["_states"]["@a"])
        self.assertNotIn(14, actor["_states"]["@a"])
        self.assertEqual(set(heal_physical_conditions(data, 1)), {5, 19, 55, 56})
        self.assertEqual(actor["_states"]["@a"], [])
        self.assertTrue(add_actor_to_party(data, 1))
        self.assertFalse(add_actor_to_party(data, 1))
        self.assertEqual(data["party"]["_actors"]["@a"], [1])

    def test_actor_name_falls_back_without_catalog_entry(self) -> None:
        data = {"actors": {"_data": {"@a": [None, {"_name": ""}]}}}
        empty_catalog = Catalog({}, {}, {}, {}, {}, {})
        self.assertEqual(actor_display_name(data, empty_catalog, 1), "Personagem 1")

    def test_validation_reports_malformed_save_without_crashing(self) -> None:
        self.assertTrue(validate_data({}))
        malformed = {
            "actors": {"_data": {"@a": "invalid"}},
            "party": {"_actors": {"@a": []}},
        }
        self.assertIn("nao e uma lista", validate_data(malformed)[0])

    def test_codec_round_trip_uses_only_a_temporary_save_copy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fh-admin-test-") as temp_dir:
            repo = build_fake_repository(Path(temp_dir))
            slot = repo.list_slots()[0]
            original_bytes = slot.path.read_bytes()
            session = repo.open_session(slot)
            try:
                self.assertEqual(validate_data(session.data), [])
                original_data = copy.deepcopy(session.data)
                backup = session.apply()
                self.assertTrue(backup.is_file())
                self.assertEqual(backup.read_bytes(), original_bytes)
                self.assertEqual(session.data, original_data)
                self.assertGreater(slot.path.stat().st_size, 0)
            finally:
                session.close()


class MutatingRoundTripCodec:
    def decode(self, input_path: Path, output_path: Path) -> None:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        if input_path.name.endswith(".modified.rpgsave"):
            data["party"]["_items"]["94"] = 999
        output_path.write_text(json.dumps(data), encoding="utf-8")

    def encode(self, input_path: Path, output_path: Path) -> None:
        shutil.copy2(input_path, output_path)


class SaveSafetyTests(unittest.TestCase):
    def test_apply_refuses_codec_round_trip_that_changes_staged_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fh-roundtrip-test-") as temp_dir:
            repo = build_fake_repository(Path(temp_dir))
            repo.codec = MutatingRoundTripCodec()
            slot = repo.list_slots()[0]
            original_bytes = slot.path.read_bytes()
            session = repo.open_session(slot)
            try:
                session.data["party"]["_items"]["94"] = 2
                session.mark_dirty()

                with self.assertRaises(SaveOperationError):
                    session.apply()

                self.assertEqual(slot.path.read_bytes(), original_bytes)
            finally:
                session.close()

    def test_restore_backup_refuses_invalid_backup_before_replacing_save(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fh-restore-test-") as temp_dir:
            repo = build_fake_repository(Path(temp_dir))
            slot = repo.list_slots()[0]
            original_bytes = slot.path.read_bytes()
            bad_backup = repo.backup_dir / "file1-20000101-000000-000000-backup.rpgsave"
            repo.backup_dir.mkdir(parents=True, exist_ok=True)
            bad_backup.write_text("{}", encoding="utf-8")

            with self.assertRaises(SaveOperationError):
                repo.restore_backup(slot, bad_backup)

            self.assertEqual(slot.path.read_bytes(), original_bytes)


class ServiceLayerTests(unittest.TestCase):
    def test_inventory_service_mutates_quantities_and_reports_result(self) -> None:
        from fh_admin_tui.services.inventory_service import InventoryService

        with tempfile.TemporaryDirectory(prefix="fh-inventory-service-") as temp_dir:
            repo = build_fake_repository(Path(temp_dir))
            session = repo.open_session(repo.list_slots()[0])
            try:
                catalog = build_test_catalog()
                service = InventoryService(catalog)

                added = service.add_entry(session.data, "items", 94, 3)
                self.assertTrue(added.changed)
                self.assertEqual(added.updated_quantity, 3)
                self.assertIn("Blue vial", added.message)

                subtracted = service.mutate_selected(session.data, "items", 94, "minus", 10)
                self.assertTrue(subtracted.changed)
                self.assertEqual(subtracted.updated_quantity, 0)
                self.assertEqual(service.current_quantity(session.data, "items", 94), 0)

                deleted = service.mutate_selected(session.data, "items", 94, "delete")
                self.assertFalse(deleted.changed)
                self.assertEqual(deleted.severity, "warning")
            finally:
                session.close()

    def test_actor_service_enforces_party_limit_and_skill_duplicates(self) -> None:
        from fh_admin_tui.services.actor_service import ActorService

        with tempfile.TemporaryDirectory(prefix="fh-actor-service-") as temp_dir:
            repo = build_fake_repository(Path(temp_dir))
            session = repo.open_session(repo.list_slots()[0])
            try:
                catalog = build_test_catalog()
                service = ActorService(catalog)
                session.data["party"]["_actors"]["@a"] = [1, 2, 3, 4]

                refused_state = service.party_action_state(session.data, 5)
                self.assertFalse(refused_state.enabled)
                self.assertIn("quatro", refused_state.reason)
                refused = service.add_to_party(session.data, 5)
                self.assertFalse(refused.changed)
                self.assertEqual(refused.severity, "warning")
                self.assertEqual(session.data["party"]["_actors"]["@a"], [1, 2, 3, 4])

                duplicate_state = service.party_action_state(session.data, 1)
                self.assertFalse(duplicate_state.enabled)
                self.assertIn("party", duplicate_state.reason)

                limb_state = service.limb_restore_action_state(1)
                self.assertTrue(limb_state.enabled)
                unsupported_limb_state = service.limb_restore_action_state(999)
                self.assertFalse(unsupported_limb_state.enabled)

                duplicate = service.add_skill(session.data, 1, 7)
                self.assertFalse(duplicate.changed)
                self.assertEqual(duplicate.severity, "warning")

                added = service.add_skill(session.data, 1, 8)
                self.assertTrue(added.changed)
                self.assertIn(8, session.data["actors"]["_data"]["@a"][1]["_skills"]["@a"])
            finally:
                session.close()

    def test_review_service_builds_diff_and_validation_errors(self) -> None:
        from fh_admin_tui.services.review_service import build_review

        with tempfile.TemporaryDirectory(prefix="fh-review-service-") as temp_dir:
            repo = build_fake_repository(Path(temp_dir))
            session = repo.open_session(repo.list_slots()[0])
            try:
                catalog = build_test_catalog()
                session.data["party"]["_items"]["94"] = 2
                session.data["party"]["_actors"]["@a"].append(999)

                review = build_review(session.baseline, session.data, catalog)

                self.assertTrue(any("Blue vial" in line for line in review.lines))
                self.assertTrue(any("party contem personagem invalido" in error for error in review.errors))
            finally:
                session.close()
