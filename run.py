#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
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


def main() -> int:
    maybe_reexec_venv()
    try:
        from fh_admin_tui.textual_app import main as app_main
    except ModuleNotFoundError as exc:
        missing = exc.name or "dependencia"
        message = [
            f"Dependencia ausente: {missing}",
            "Crie a venv local e instale os pacotes:",
            "  python3 -m venv .venv",
            "  .venv/bin/python -m ensurepip --upgrade",
            "  .venv/bin/python -m pip install -r requirements.txt",
        ]
        print("\n".join(message), file=sys.stderr)
        return 1
    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
