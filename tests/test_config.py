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


class RunCliTests(unittest.TestCase):
    def test_parse_args_accepts_setup_command(self) -> None:
        from run import parse_args

        self.assertEqual(parse_args(["setup"]).command, "setup")

    def test_user_path_input_accepts_shell_escaped_home_relative_path(self) -> None:
        from run import resolve_user_path

        parsed = resolve_user_path(r"pendrive/@home/kim/.local/share/Steam/steamapps/common/Fear\ \&\ Hunger/www")

        self.assertEqual(parsed, Path.home() / "pendrive" / "@home" / "kim" / ".local" / "share" / "Steam" / "steamapps" / "common" / "Fear & Hunger" / "www")


class CliConfigTests(unittest.TestCase):
    def test_local_env_file_round_trip_quotes_paths(self) -> None:
        from fh_admin_tui.cli_config import load_local_env_file, write_local_env_file

        with tempfile.TemporaryDirectory(prefix="fh-cli-config-") as temp_dir:
            target = Path(temp_dir) / ".fh-admin-tui.env"
            values = {
                "FH_GAME_ROOT": str(Path(temp_dir) / "Fear & Hunger" / "www"),
                "FH_BACKUP_DIR": str(Path(temp_dir) / "fear and hunger saves"),
            }

            write_local_env_file(target, values)
            loaded = load_local_env_file(target)

            self.assertEqual(loaded, values)
            self.assertIn("FH_GAME_ROOT=", target.read_text(encoding="utf-8"))

    def test_local_env_file_ignores_comments_and_malformed_lines(self) -> None:
        from fh_admin_tui.cli_config import load_local_env_file

        with tempfile.TemporaryDirectory(prefix="fh-cli-config-") as temp_dir:
            target = Path(temp_dir) / ".fh-admin-tui.env"
            target.write_text("# comentario\nFH_GAME_ROOT=/tmp/game\nlinha ruim\n", encoding="utf-8")

            self.assertEqual(load_local_env_file(target), {"FH_GAME_ROOT": "/tmp/game"})


class DoctorTests(unittest.TestCase):
    def test_doctor_reports_ok_for_complete_fake_runtime(self) -> None:
        from fh_admin_tui.doctor import run_diagnostics

        with tempfile.TemporaryDirectory(prefix="fh-doctor-ok-") as temp_dir:
            root = Path(temp_dir)
            game_root = root / "game" / "www"
            save_dir = game_root / "save"
            data_dir = game_root / "data"
            lz_path = game_root / "js" / "libs" / "lz-string.js"
            codec_script = root / "codec" / "rpgsave_codec.js"
            backup_dir = root / "backups"
            save_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)
            for name in ("Items.json", "Weapons.json", "Armors.json", "Skills.json", "Actors.json", "States.json"):
                (data_dir / name).write_text("[]", encoding="utf-8")
            lz_path.parent.mkdir(parents=True)
            lz_path.write_text("module.exports = {};", encoding="utf-8")
            codec_script.parent.mkdir(parents=True)
            codec_script.write_text("#!/usr/bin/env node\n", encoding="utf-8")
            config = AppConfig.from_env(
                {
                    "FH_GAME_ROOT": str(game_root),
                    "FH_CODEC_SCRIPT": str(codec_script),
                    "FH_BACKUP_DIR": str(backup_dir),
                }
            )

            report = run_diagnostics(config, node_path="node")

            self.assertTrue(report.ok)
            self.assertTrue(all(check.ok for check in report.checks))
            self.assertTrue(backup_dir.is_dir())

    def test_doctor_reports_actionable_missing_paths(self) -> None:
        from fh_admin_tui.doctor import run_diagnostics

        with tempfile.TemporaryDirectory(prefix="fh-doctor-missing-") as temp_dir:
            root = Path(temp_dir)
            config = AppConfig.from_env(
                {
                    "FH_GAME_ROOT": str(root / "missing" / "www"),
                    "FH_CODEC_SCRIPT": str(root / "missing-codec.js"),
                    "FH_BACKUP_DIR": str(root / "backups"),
                }
            )

            report = run_diagnostics(config, node_path=None)

            self.assertFalse(report.ok)
            rendered = "\n".join(check.message for check in report.checks)
            self.assertIn("FH_GAME_ROOT", rendered)
            self.assertIn("FH_CODEC_SCRIPT", rendered)
            self.assertIn("Node.js", rendered)

    def test_doctor_reports_missing_catalog_json_files(self) -> None:
        from fh_admin_tui.doctor import run_diagnostics

        with tempfile.TemporaryDirectory(prefix="fh-doctor-catalog-") as temp_dir:
            root = Path(temp_dir)
            game_root = root / "game" / "www"
            (game_root / "save").mkdir(parents=True)
            (game_root / "data").mkdir(parents=True)
            lz_path = game_root / "js" / "libs" / "lz-string.js"
            lz_path.parent.mkdir(parents=True)
            lz_path.write_text("module.exports = {};", encoding="utf-8")
            config = AppConfig.from_env({"FH_GAME_ROOT": str(game_root), "FH_BACKUP_DIR": str(root / "backups")})

            report = run_diagnostics(config, node_path="node")

            self.assertFalse(report.ok)
            rendered = "\n".join(check.message for check in report.checks)
            self.assertIn("Items.json", rendered)
            self.assertIn("FH_DATA_DIR", rendered)
