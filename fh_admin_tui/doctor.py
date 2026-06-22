from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig

REQUIRED_CATALOG_FILES = ("Items.json", "Weapons.json", "Armors.json", "Skills.json", "Actors.json", "States.json")


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    ok: bool
    message: str


@dataclass(frozen=True)
class DiagnosticReport:
    checks: list[DiagnosticCheck]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def run_diagnostics(config: AppConfig, node_path: str | None = None) -> DiagnosticReport:
    node = node_path if node_path is not None else shutil.which("node")
    checks = [
        _path_check("game root", config.game_root, config.game_root.is_dir(), "Configure FH_GAME_ROOT ou use --game-root."),
        _path_check("save dir", config.save_dir, config.save_dir.is_dir(), "Configure FH_SAVE_DIR ou confira FH_GAME_ROOT/save."),
        _path_check("data dir", config.data_dir, config.data_dir.is_dir(), "Configure FH_DATA_DIR ou confira FH_GAME_ROOT/data."),
        _catalog_files_check(config.data_dir),
        _path_check("lz-string", config.lz_string_path, config.lz_string_path.is_file(), "Confira se FH_GAME_ROOT aponta para a pasta www do jogo."),
        _path_check("codec script", config.codec_script, config.codec_script.is_file(), "Configure FH_CODEC_SCRIPT ou reinstale o pacote."),
        DiagnosticCheck("node", bool(node), f"Node.js encontrado: {node}" if node else "Node.js nao encontrado no PATH. Instale nodejs."),
        _backup_check(config.backup_dir),
    ]
    return DiagnosticReport(checks)


def format_report(report: DiagnosticReport) -> str:
    lines = ["Diagnostico FH Admin TUI"]
    for check in report.checks:
        prefix = "OK" if check.ok else "ERRO"
        lines.append(f"[{prefix}] {check.name}: {check.message}")
    lines.append("Resultado: OK" if report.ok else "Resultado: existem problemas para corrigir")
    return "\n".join(lines)


def _path_check(name: str, path: Path, ok: bool, hint: str) -> DiagnosticCheck:
    if ok:
        return DiagnosticCheck(name, True, str(path))
    return DiagnosticCheck(name, False, f"nao encontrado: {path}. {hint}")


def _backup_check(path: Path) -> DiagnosticCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="fh-admin-doctor-", dir=path, delete=True):
            pass
    except OSError as exc:
        return DiagnosticCheck("backup dir", False, f"sem permissao de escrita em {path}: {exc}. Configure FH_BACKUP_DIR.")
    return DiagnosticCheck("backup dir", True, str(path))


def _catalog_files_check(data_dir: Path) -> DiagnosticCheck:
    missing = [name for name in REQUIRED_CATALOG_FILES if not (data_dir / name).is_file()]
    if not missing:
        return DiagnosticCheck("catalog data", True, f"arquivos de catalogo encontrados em {data_dir}")
    rendered = ", ".join(missing)
    return DiagnosticCheck(
        "catalog data",
        False,
        f"arquivos ausentes em {data_dir}: {rendered}. Configure FH_DATA_DIR ou use --game-root apontando para a pasta www correta.",
    )
