from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fh_admin_tui.config import AppConfig


class ConfigTests(unittest.TestCase):
    def test_env_paths_override_defaults_without_machine_specific_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fh-config-test-") as temp_dir:
            root = Path(temp_dir)
            env = {
                "FH_GAME_ROOT": str(root / "game" / "www"),
                "FH_SAVE_DIR": str(root / "saves"),
                "FH_DATA_DIR": str(root / "data"),
                "FH_CODEC_SCRIPT": str(root / "codec.js"),
                "FH_BACKUP_DIR": str(root / "backups"),
            }
            config = AppConfig.from_env(env)

            self.assertEqual(config.game_root, root / "game" / "www")
            self.assertEqual(config.save_dir, root / "saves")
            self.assertEqual(config.data_dir, root / "data")
            self.assertEqual(config.codec_script, root / "codec.js")
            self.assertEqual(config.backup_dir, root / "backups")

    def test_save_and_data_default_from_game_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fh-config-root-") as temp_dir:
            game_root = Path(temp_dir) / "Fear & Hunger" / "www"
            config = AppConfig.from_env({"FH_GAME_ROOT": str(game_root)})

            self.assertEqual(config.save_dir, game_root / "save")
            self.assertEqual(config.data_dir, game_root / "data")
            self.assertEqual(config.lz_string_path, game_root / "js" / "libs" / "lz-string.js")
            self.assertEqual(config.codec_script.name, "rpgsave_codec.js")
            self.assertTrue(config.codec_script.is_file())

    def test_game_root_override_moves_default_save_and_data_dirs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fh-config-override-") as temp_dir:
            root = Path(temp_dir)
            original_root = root / "original" / "www"
            override_root = root / "override" / "www"
            config = AppConfig.from_env({"FH_GAME_ROOT": str(original_root)})

            updated = config.with_overrides(game_root=override_root)

            self.assertEqual(updated.game_root, override_root)
            self.assertEqual(updated.save_dir, override_root / "save")
            self.assertEqual(updated.data_dir, override_root / "data")
            self.assertEqual(updated.lz_string_path, override_root / "js" / "libs" / "lz-string.js")

    def test_game_root_override_keeps_explicit_save_and_data_dirs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fh-config-explicit-") as temp_dir:
            root = Path(temp_dir)
            original_root = root / "original" / "www"
            explicit_save = root / "custom-save"
            explicit_data = root / "custom-data"
            override_root = root / "override" / "www"
            config = AppConfig.from_env(
                {
                    "FH_GAME_ROOT": str(original_root),
                    "FH_SAVE_DIR": str(explicit_save),
                    "FH_DATA_DIR": str(explicit_data),
                }
            )

            updated = config.with_overrides(game_root=override_root)

            self.assertEqual(updated.save_dir, explicit_save)
            self.assertEqual(updated.data_dir, explicit_data)
