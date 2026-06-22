from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .config import AppConfig
from .mutations import validate_data


class SaveOperationError(RuntimeError):
    pass


class SaveCodec(Protocol):
    def decode(self, input_path: Path, output_path: Path) -> None:
        ...

    def encode(self, input_path: Path, output_path: Path) -> None:
        ...


class NodeSaveCodec:
    def __init__(self, codec_script: Path, lz_string_path: Path) -> None:
        self.codec_script = codec_script
        self.lz_string_path = lz_string_path

    def decode(self, input_path: Path, output_path: Path) -> None:
        _run_codec("decode", input_path, output_path, self.codec_script, self.lz_string_path)

    def encode(self, input_path: Path, output_path: Path) -> None:
        _run_codec("encode", input_path, output_path, self.codec_script, self.lz_string_path)


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
        save_dir: Path | None = None,
        data_dir: Path | None = None,
        lz_string_path: Path | None = None,
        codec_script: Path | None = None,
        backup_dir: Path | None = None,
        codec: SaveCodec | None = None,
        config: AppConfig | None = None,
    ) -> None:
        resolved = config or AppConfig.from_env()
        self.save_dir = save_dir or resolved.save_dir
        self.data_dir = data_dir or resolved.data_dir
        self.lz_string_path = lz_string_path or resolved.lz_string_path
        self.codec_script = codec_script or resolved.codec_script
        self.backup_dir = backup_dir or resolved.backup_dir
        self.codec = codec or NodeSaveCodec(self.codec_script, self.lz_string_path)

    @classmethod
    def from_config(cls, config: AppConfig) -> "SaveRepository":
        return cls(config=config)

    def list_slots(self) -> list[SaveSlot]:
        if not self.save_dir.is_dir():
            raise SaveOperationError(f"Pasta de saves nao encontrada: {self.save_dir}")
        slots: list[SaveSlot] = []
        for path in sorted(self.save_dir.glob("file*.rpgsave"), key=_slot_sort_key):
            stem = path.stem
            number_text = stem.removeprefix("file")
            if number_text.isdigit():
                slots.append(SaveSlot(int(number_text), path))
        return slots

    def create_backup(self, slot: SaveSlot) -> Path:
        if not slot.path.is_file():
            raise SaveOperationError(f"Save nao encontrado: {slot.path}")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = self.backup_dir / f"file{slot.number}-{timestamp}-backup.rpgsave"
        shutil.copy2(slot.path, backup_path)
        return backup_path

    def list_backups(self, slot: SaveSlot) -> list[Path]:
        if not self.backup_dir.exists():
            return []
        pattern = f"file{slot.number}-*-backup.rpgsave"
        return sorted(self.backup_dir.glob(pattern), reverse=True)

    def restore_backup(self, slot: SaveSlot, backup_path: Path) -> Path:
        if not backup_path.is_file():
            raise SaveOperationError(f"Backup nao encontrado: {backup_path}")
        self.validate_encoded_save(backup_path, f"backup {backup_path.name}")
        safety_backup = self.create_backup(slot)
        _atomic_copy(backup_path, slot.path)
        return safety_backup

    def open_session(self, slot: SaveSlot) -> "SaveSession":
        return SaveSession(self, slot)

    def decode(self, input_path: Path, output_path: Path) -> None:
        self.codec.decode(input_path, output_path)

    def encode(self, input_path: Path, output_path: Path) -> None:
        self.codec.encode(input_path, output_path)

    def validate_encoded_save(self, encoded_path: Path, context: str) -> dict:
        with tempfile.TemporaryDirectory(prefix="fh-validate-") as temp_dir:
            decoded_path = Path(temp_dir) / "decoded.json"
            self.decode(encoded_path, decoded_path)
            data = load_json_like(decoded_path)
        errors = validate_data(data)
        if errors:
            raise SaveOperationError(f"{context} invalido: " + "; ".join(errors[:10]))
        return data


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
        self._closed = False
        self.reload()

    def reload(self) -> None:
        if self._closed:
            raise SaveOperationError("A sessao deste slot ja foi fechada")
        self.repo.decode(self.slot.path, self.decoded_path)
        self.data = load_json_like(self.decoded_path)
        self.baseline = copy.deepcopy(self.data)
        self.dirty = False

    def mark_dirty(self) -> None:
        self.dirty = True

    def apply(self) -> Path:
        if self._closed:
            raise SaveOperationError("A sessao deste slot ja foi fechada")
        errors = validate_data(self.data)
        if errors:
            raise ValueError("validacao falhou: " + "; ".join(errors[:10]))
        backup_path = self.repo.create_backup(self.slot)
        dump_json_like(self.data, self.decoded_path)
        self.repo.encode(self.decoded_path, self.encoded_path)
        self.repo.decode(self.encoded_path, self.validation_path)
        round_trip_data = load_json_like(self.validation_path)
        round_trip_errors = validate_data(round_trip_data)
        if round_trip_errors:
            raise SaveOperationError("codec gerou save invalido: " + "; ".join(round_trip_errors[:10]))
        if round_trip_data != self.data:
            raise SaveOperationError("codec round-trip alterou os dados staged; save original preservado")
        _atomic_copy(self.encoded_path, self.slot.path)
        self.baseline = copy.deepcopy(self.data)
        self.dirty = False
        return backup_path

    def close(self) -> None:
        if not self._closed:
            self._tmpdir.cleanup()
            self._closed = True


def _slot_sort_key(path: Path) -> tuple[int, str]:
    stem = path.stem
    number_text = stem.removeprefix("file")
    return (int(number_text) if number_text.isdigit() else 10**9, path.name)


def _run_codec(mode: str, input_path: Path, output_path: Path, codec_script: Path, lz_string_path: Path) -> None:
    if mode not in {"decode", "encode"}:
        raise ValueError(f"Modo de codec invalido: {mode}")
    for label, path in (
        ("entrada", input_path),
        ("script do codec", codec_script),
        ("lz-string", lz_string_path),
    ):
        if not path.is_file():
            raise SaveOperationError(f"Arquivo de {label} nao encontrado: {path}")
    try:
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
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise SaveOperationError("Node.js nao foi encontrado no PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise SaveOperationError(f"Codec excedeu 30 segundos durante {mode}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise SaveOperationError(f"Codec falhou durante {mode}: {detail}") from exc
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise SaveOperationError(f"Codec nao gerou uma saida valida durante {mode}")


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.fh-admin-",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
