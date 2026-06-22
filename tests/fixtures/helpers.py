from __future__ import annotations

import shutil
from pathlib import Path

from fh_admin_tui.catalog import Catalog, Entry
from fh_admin_tui.save_ops import SaveRepository

FIXTURE_DIR = Path(__file__).resolve().parent
MINIMAL_SAVE = FIXTURE_DIR / "minimal_save.json"


class CopyCodec:
    def decode(self, input_path: Path, output_path: Path) -> None:
        shutil.copy2(input_path, output_path)

    def encode(self, input_path: Path, output_path: Path) -> None:
        shutil.copy2(input_path, output_path)


def build_fake_repository(root: Path) -> SaveRepository:
    save_dir = root / "save"
    data_dir = root / "data"
    backup_dir = root / "backups"
    save_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MINIMAL_SAVE, save_dir / "file1.rpgsave")
    return SaveRepository(
        save_dir=save_dir,
        data_dir=data_dir,
        lz_string_path=data_dir / "lz-string.js",
        codec_script=data_dir / "rpgsave_codec.js",
        backup_dir=backup_dir,
        codec=CopyCodec(),
    )


def build_test_catalog() -> Catalog:
    return Catalog(
        items={1: Entry(1, "Potion", "Heals a little."), 94: Entry(94, "Blue vial", "Fixture item.")},
        weapons={2: Entry(2, "Short sword", "Fixture weapon.")},
        armors={3: Entry(3, "Leather vest", "Fixture armor.")},
        skills={7: Entry(7, "Dash", "Known skill."), 8: Entry(8, "Counter", "Fixture skill.")},
        actors={1: Entry(1, "Cahara", "Fixture actor.")},
        states={3: Entry(3, "Arm cut", ""), 55: Entry(55, "Infection", "")},
    )
