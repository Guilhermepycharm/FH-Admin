#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path


def maybe_reexec_venv() -> None:
    project_root = Path(__file__).resolve().parent
    venv_root = project_root / ".venv"
    venv_python = project_root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return
    if Path(sys.prefix).resolve() == venv_root.resolve():
        return
    os.execv(str(venv_python), [str(venv_python), str(project_root / "run.py"), *sys.argv[1:]])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fear & Hunger Admin TUI")
    parser.add_argument("--game-root", type=Path, help="Diretorio www do jogo. Tambem pode usar FH_GAME_ROOT.")
    parser.add_argument("--save-dir", type=Path, help="Diretorio de saves. Tambem pode usar FH_SAVE_DIR.")
    parser.add_argument("--data-dir", type=Path, help="Diretorio data do jogo. Tambem pode usar FH_DATA_DIR.")
    parser.add_argument("--codec-script", type=Path, help="Script rpgsave_codec.js. Tambem pode usar FH_CODEC_SCRIPT.")
    parser.add_argument("--backup-dir", type=Path, help="Diretorio de backups. Tambem pode usar FH_BACKUP_DIR.")
    return parser.parse_args(argv)


def main() -> int:
    maybe_reexec_venv()
    args = parse_args(sys.argv[1:])
    try:
        from fh_admin_tui.config import AppConfig
        from fh_admin_tui.diagnostics import configure_logging, get_logger

        log_path = configure_logging()
        logger = get_logger("launcher")
        config = AppConfig.from_env().with_overrides(
            game_root=args.game_root,
            save_dir=args.save_dir,
            data_dir=args.data_dir,
            codec_script=args.codec_script,
            backup_dir=args.backup_dir,
        )
        from fh_admin_tui.textual_app import main as app_main
    except ModuleNotFoundError as exc:
        missing = exc.name or "dependencia"
        message = [
            f"Dependencia ausente: {missing}",
            "Crie a venv local e instale o projeto:",
            "  python3 -m venv .venv",
            "  .venv/bin/python -m ensurepip --upgrade",
            "  .venv/bin/python -m pip install -e '.[dev]'",
        ]
        print("\n".join(message), file=sys.stderr)
        return 1
    except Exception:
        traceback.print_exc()
        return 1

    try:
        return app_main(config)
    except KeyboardInterrupt:
        logger.info("Aplicacao interrompida pelo usuario")
        return 130
    except Exception:
        logger.exception("Falha fatal durante a execucao")
        print(f"Falha fatal. Detalhes registrados em {log_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
