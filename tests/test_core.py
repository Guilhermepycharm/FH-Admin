from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from fh_admin_tui.catalog import Catalog
from fh_admin_tui.mutations import actor_display_name, validate_data
from fh_admin_tui.save_ops import SaveRepository


class CoreTests(unittest.TestCase):
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
