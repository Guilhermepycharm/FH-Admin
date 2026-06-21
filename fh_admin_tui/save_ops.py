from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .mutations import validate_data


GAME_ROOT = Path("/home/kim/.local/share/Steam/steamapps/common/Fear & Hunger/www")
SAVE_DIR = GAME_ROOT / "save"
DATA_DIR = GAME_ROOT / "data"
LZ_STRING_PATH = GAME_ROOT / "js" / "libs" / "lz-string.js"
CODEC_SCRIPT = Path("/home/kim/.codex/skills/fh-save-editor/scripts/rpgsave_codec.js")
BACKUP_DIR = Path.home() / "fear and hunger saves"


def load_json_like(path: Path) -> dict:
    return json.JSONDecoder(strict=False).decode(path.read_text(encoding="utf-8"))


def dump_json_like(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


@dataclass
class SaveSlot:
    number: int
    path: Path


class SaveRepository:
    def __init__(
        self,
        save_dir: Path = SAVE_DIR,
        data_dir: Path = DATA_DIR,
        lz_string_path: Path = LZ_STRING_PATH,
        codec_script: Path = CODEC_SCRIPT,
        backup_dir: Path = BACKUP_DIR,
    ) -> None:
        self.save_dir = save_dir
        self.data_dir = data_dir
        self.lz_string_path = lz_string_path
        self.codec_script = codec_script
        self.backup_dir = backup_dir

    def list_slots(self) -> list[SaveSlot]:
        slots: list[SaveSlot] = []
        for path in sorted(self.save_dir.glob("file*.rpgsave"), key=_slot_sort_key):
            stem = path.stem
            number_text = stem.removeprefix("file")
            if number_text.isdigit():
                slots.append(SaveSlot(int(number_text), path))
        return slots

    def create_backup(self, slot: SaveSlot) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = self.backup_dir / f"file{slot.number}-{timestamp}-backup.rpgsave"
        shutil.copy2(slot.path, backup_path)
        return backup_path

    def list_backups(self, slot: SaveSlot) -> list[Path]:
        if not self.backup_dir.exists():
            return []
        pattern = f"file{slot.number}-*-backup.rpgsave"
        return sorted(self.backup_dir.glob(pattern), reverse=True)

    def restore_backup(self, slot: SaveSlot, backup_path: Path) -> Path:
        safety_backup = self.create_backup(slot)
        shutil.copy2(backup_path, slot.path)
        return safety_backup

    def open_session(self, slot: SaveSlot) -> "SaveSession":
        return SaveSession(self, slot)

    def decode(self, input_path: Path, output_path: Path) -> None:
        _run_codec("decode", input_path, output_path, self.codec_script, self.lz_string_path)

    def encode(self, input_path: Path, output_path: Path) -> None:
        _run_codec("encode", input_path, output_path, self.codec_script, self.lz_string_path)


class SaveSession:
    def __init__(self, repo: SaveRepository, slot: SaveSlot) -> None:
        self.repo = repo
        self.slot = slot
        self._tmpdir = tempfile.TemporaryDirectory(prefix=f"fh-slot{slot.number}-")
        self.temp_dir = Path(self._tmpdir.name)
        self.decoded_path = self.temp_dir / f"file{slot.number}.rpgsave.txt"
        self.encoded_path = self.temp_dir / f"file{slot.number}.modified.rpgsave"
        self.validation_path = self.temp_dir / f"file{slot.number}.validated.txt"
        self.data: dict = {}
        self.baseline: dict = {}
        self.dirty = False
        self.reload()

    def reload(self) -> None:
        self.repo.decode(self.slot.path, self.decoded_path)
        self.data = load_json_like(self.decoded_path)
        self.baseline = copy.deepcopy(self.data)
        self.dirty = False

    def mark_dirty(self) -> None:
        self.dirty = True

    def apply(self) -> Path:
        errors = validate_data(self.data)
        if errors:
            raise ValueError("validacao falhou: " + "; ".join(errors[:10]))
        backup_path = self.repo.create_backup(self.slot)
        dump_json_like(self.data, self.decoded_path)
        self.repo.encode(self.decoded_path, self.encoded_path)
        self.repo.decode(self.encoded_path, self.validation_path)
        load_json_like(self.validation_path)
        shutil.copy2(self.encoded_path, self.slot.path)
        self.baseline = copy.deepcopy(self.data)
        self.dirty = False
        return backup_path

    def close(self) -> None:
        self._tmpdir.cleanup()


def _slot_sort_key(path: Path) -> tuple[int, str]:
    stem = path.stem
    number_text = stem.removeprefix("file")
    return (int(number_text) if number_text.isdigit() else 10**9, path.name)


def _run_codec(mode: str, input_path: Path, output_path: Path, codec_script: Path, lz_string_path: Path) -> None:
    subprocess.run(
        [
            "node",
            str(codec_script),
            mode,
            str(input_path),
            str(output_path),
            str(lz_string_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
