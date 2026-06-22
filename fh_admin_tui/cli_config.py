from __future__ import annotations

import shlex
from pathlib import Path
from typing import Mapping

LOCAL_ENV_FILE = ".fh-admin-tui.env"
LOCAL_ENV_KEYS = ("FH_GAME_ROOT", "FH_SAVE_DIR", "FH_DATA_DIR", "FH_CODEC_SCRIPT", "FH_BACKUP_DIR")


def load_local_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if key not in LOCAL_ENV_KEYS:
            continue
        try:
            parsed = shlex.split(raw_value, posix=True)
        except ValueError:
            continue
        values[key] = parsed[0] if parsed else ""
    return values


def write_local_env_file(path: Path, values: Mapping[str, str]) -> None:
    lines = [
        "# Configuracao local do FH Admin TUI.",
        "# Este arquivo nao deve ser commitado.",
    ]
    for key in LOCAL_ENV_KEYS:
        value = values.get(key)
        if value:
            lines.append(f"{key}={shlex.quote(str(value))}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def merge_local_env(environ: Mapping[str, str], local_values: Mapping[str, str]) -> dict[str, str]:
    merged = dict(local_values)
    merged.update(environ)
    return merged
