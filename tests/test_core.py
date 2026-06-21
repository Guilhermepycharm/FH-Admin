from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from fh_admin_tui.catalog import Catalog
from fh_admin_tui.mutations import (
    actor_display_name,
    add_actor_to_party,
    heal_physical_conditions,
    restore_supported_limbs,
    validate_data,
)
from fh_admin_tui.save_ops import SaveRepository


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
        self.assertEqual(actor_display_name(data, empty_catalog, 1), "Actor 1")

    def test_validation_reports_malformed_save_without_crashing(self) -> None:
        self.assertTrue(validate_data({}))
        malformed = {
            "actors": {"_data": {"@a": "invalid"}},
            "party": {"_actors": {"@a": []}},
        }
        self.assertIn("nao e uma lista", validate_data(malformed)[0])

    def test_codec_round_trip_uses_only_a_temporary_save_copy(self) -> None:
        source_repo = SaveRepository()
        slots = source_repo.list_slots()
        if not slots:
            self.skipTest("Nenhum save local disponivel para testar o codec")

        with tempfile.TemporaryDirectory(prefix="fh-admin-test-") as temp_dir:
            root = Path(temp_dir)
            save_dir = root / "save"
            save_dir.mkdir()
            copied_save = save_dir / slots[0].path.name
            shutil.copy2(slots[0].path, copied_save)
            repo = SaveRepository(
                save_dir=save_dir,
                data_dir=source_repo.data_dir,
                lz_string_path=source_repo.lz_string_path,
                codec_script=source_repo.codec_script,
                backup_dir=root / "backups",
            )
            session = repo.open_session(repo.list_slots()[0])
            try:
                self.assertEqual(validate_data(session.data), [])
                original = copy.deepcopy(session.data)
                backup = session.apply()
                self.assertTrue(backup.is_file())
                self.assertEqual(session.data, original)
                self.assertGreater(copied_save.stat().st_size, 0)
            finally:
                session.close()
