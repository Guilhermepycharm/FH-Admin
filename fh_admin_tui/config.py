from __future__ import annotations

import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Mapping


ENV_GAME_ROOT = "FH_GAME_ROOT"
ENV_SAVE_DIR = "FH_SAVE_DIR"
ENV_DATA_DIR = "FH_DATA_DIR"
ENV_CODEC_SCRIPT = "FH_CODEC_SCRIPT"
ENV_BACKUP_DIR = "FH_BACKUP_DIR"


def _expand_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve()


def _default_game_root() -> Path:
    return Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common" / "Fear & Hunger" / "www"


def _default_codec_script() -> Path:
    return Path(str(files("fh_admin_tui").joinpath("resources", "rpgsave_codec.js")))


@dataclass(frozen=True)
class AppConfig:
    game_root: Path
    save_dir: Path
    data_dir: Path
    lz_string_path: Path
    codec_script: Path
    backup_dir: Path

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AppConfig":
        env = os.environ if environ is None else environ
        game_root = _expand_path(env.get(ENV_GAME_ROOT, _default_game_root()))
        save_dir = _expand_path(env.get(ENV_SAVE_DIR, game_root / "save"))
        data_dir = _expand_path(env.get(ENV_DATA_DIR, game_root / "data"))
        codec_script = _expand_path(env.get(ENV_CODEC_SCRIPT, _default_codec_script()))
        backup_dir = _expand_path(env.get(ENV_BACKUP_DIR, Path.home() / "fear and hunger saves"))
        return cls(
            game_root=game_root,
            save_dir=save_dir,
            data_dir=data_dir,
            lz_string_path=game_root / "js" / "libs" / "lz-string.js",
            codec_script=codec_script,
            backup_dir=backup_dir,
        )

    def with_overrides(
        self,
        *,
        game_root: Path | None = None,
        save_dir: Path | None = None,
        data_dir: Path | None = None,
        codec_script: Path | None = None,
        backup_dir: Path | None = None,
    ) -> "AppConfig":
        resolved_game_root = _expand_path(game_root) if game_root is not None else self.game_root
        current_save_is_default = self.save_dir == self.game_root / "save"
        current_data_is_default = self.data_dir == self.game_root / "data"

        if save_dir is not None:
            resolved_save_dir = _expand_path(save_dir)
        elif game_root is not None and current_save_is_default:
            resolved_save_dir = resolved_game_root / "save"
        else:
            resolved_save_dir = self.save_dir

        if data_dir is not None:
            resolved_data_dir = _expand_path(data_dir)
        elif game_root is not None and current_data_is_default:
            resolved_data_dir = resolved_game_root / "data"
        else:
            resolved_data_dir = self.data_dir

        return AppConfig(
            game_root=resolved_game_root,
            save_dir=resolved_save_dir,
            data_dir=resolved_data_dir,
            lz_string_path=resolved_game_root / "js" / "libs" / "lz-string.js",
            codec_script=_expand_path(codec_script) if codec_script is not None else self.codec_script,
            backup_dir=_expand_path(backup_dir) if backup_dir is not None else self.backup_dir,
        )

    def validate_for_runtime(self) -> list[str]:
        checks = (
            ("pasta de saves", self.save_dir, "is_dir"),
            ("pasta de dados", self.data_dir, "is_dir"),
            ("script do codec", self.codec_script, "is_file"),
            ("lz-string", self.lz_string_path, "is_file"),
        )
        errors: list[str] = []
        for label, path, predicate in checks:
            ok = path.is_dir() if predicate == "is_dir" else path.is_file()
            if not ok:
                errors.append(f"{label} nao encontrado: {path}")
        return errors
