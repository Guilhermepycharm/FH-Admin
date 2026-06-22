#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
import shlex
import traceback
from pathlib import Path


def maybe_reexec_venv() -> None:
    project_root = Path(__file__).resolve().parent
    venv_root = project_root / ".venv"
    venv_python = project_root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        if venv_python.is_symlink():
            print(
                "Aviso: .venv/bin/python existe como symlink quebrado; rode scripts/install-linux.sh para recriar a venv.",
                file=sys.stderr,
            )
        return
    if not os.access(venv_python, os.X_OK):
        print("Aviso: .venv/bin/python nao e executavel; rode scripts/install-linux.sh.", file=sys.stderr)
        return
    if Path(sys.prefix).resolve() == venv_root.resolve():
        return
    os.execv(str(venv_python), [str(venv_python), str(project_root / "run.py"), *sys.argv[1:]])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fear & Hunger Admin TUI")
    parser.add_argument("command", nargs="?", choices=("doctor", "configure", "setup"), help="Comando opcional de diagnostico/configuracao.")
    parser.add_argument("--game-root", type=Path, help="Diretorio www do jogo. Tambem pode usar FH_GAME_ROOT.")
    parser.add_argument("--save-dir", type=Path, help="Diretorio de saves. Tambem pode usar FH_SAVE_DIR.")
    parser.add_argument("--data-dir", type=Path, help="Diretorio data do jogo. Tambem pode usar FH_DATA_DIR.")
    parser.add_argument("--codec-script", type=Path, help="Script rpgsave_codec.js. Tambem pode usar FH_CODEC_SCRIPT.")
    parser.add_argument("--backup-dir", type=Path, help="Diretorio de backups. Tambem pode usar FH_BACKUP_DIR.")
    return parser.parse_args(argv)


def resolve_user_path(value: str) -> Path:
    parsed = shlex.split(value.strip(), posix=True)
    raw = parsed[0] if parsed else value.strip()
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    home_relative = (Path.home() / path).resolve()
    if home_relative.exists() or raw.startswith(("pendrive/", "Downloads/", "Documents/", "Desktop/")):
        return home_relative
    return path.resolve()


def _prompt_path(label: str, current: Path, *, must_exist: bool = False, hint: str | None = None) -> Path:
    while True:
        print(f"\n{label}")
        if hint:
            print(hint)
        print(f"Atual: {current}")
        value = input("Digite o caminho, Enter para manter, ou q para cancelar: ").strip()
        if value.casefold() in {"q", "quit", "sair"}:
            raise EOFError
        path = resolve_user_path(value) if value else current
        if not must_exist or path.exists():
            return path
        print(f"Nao encontrei esse caminho: {path}")
        print("Dica: use o caminho completo, por exemplo /home/kim/pendrive/.../Fear & Hunger/www")
        print("No prompt nao precisa escapar espacos com barra; pode colar Fear & Hunger normalmente.")


def _confirm(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {suffix}: ").strip().casefold()
    if not answer:
        return default
    return answer in {"y", "yes", "s", "sim"}


def _menu(title: str, choices: list[tuple[str, str]]) -> str:
    print(f"\n{title}")
    for index, (label, _) in enumerate(choices, start=1):
        print(f"  {index}. {label}")
    while True:
        answer = input("Escolha uma opcao: ").strip().casefold()
        if answer in {"q", "quit", "sair"}:
            return "exit"
        if answer.isdigit():
            position = int(answer)
            if 1 <= position <= len(choices):
                return choices[position - 1][1]
        for label, value in choices:
            if answer == value or answer == label.casefold():
                return value
        print("Opcao invalida. Digite o numero da opcao, ou q para sair.")


def _print_setup_intro() -> None:
    print("\nFH Admin TUI - Setup")
    print("Configure uma vez, depois rode 'fh admin tui' ou 'fh-admin-tui'.")


def _save_config(config, local_env_path: Path, *, game_root: Path, save_dir: Path, data_dir: Path, backup_dir: Path) -> int:
    from fh_admin_tui.cli_config import write_local_env_file
    from fh_admin_tui.doctor import format_report, run_diagnostics

    values = {
        "FH_GAME_ROOT": str(game_root),
        "FH_SAVE_DIR": str(save_dir),
        "FH_DATA_DIR": str(data_dir),
        "FH_BACKUP_DIR": str(backup_dir),
    }
    write_local_env_file(local_env_path, values)
    configured = config.with_overrides(game_root=game_root, save_dir=save_dir, data_dir=data_dir, backup_dir=backup_dir)
    print(f"\nConfiguracao salva em {local_env_path}")
    print(format_report(run_diagnostics(configured)))
    return 0


def _manual_config(config, local_env_path: Path) -> int:
    try:
        game_root = _prompt_path(
            "Pasta www do Fear & Hunger",
            config.game_root,
            must_exist=True,
            hint="Exemplo: /home/kim/pendrive/@home/kim/.local/share/Steam/steamapps/common/Fear & Hunger/www",
        )
        save_dir = _prompt_path("Pasta de saves", game_root / "save", hint="Normalmente e: <www>/save")
        data_dir = _prompt_path("Pasta data", game_root / "data", hint="Normalmente e: <www>/data")
        backup_dir = _prompt_path(
            "Pasta para backups automaticos",
            config.backup_dir,
            hint="Pode deixar o padrao; a pasta sera criada quando necessario.",
        )
    except EOFError:
        print("Configuracao cancelada.", file=sys.stderr)
        return 130
    return _save_config(config, local_env_path, game_root=game_root, save_dir=save_dir, data_dir=data_dir, backup_dir=backup_dir)


def run_configure(config, local_env_path: Path) -> int:
    _print_setup_intro()
    return _manual_config(config, local_env_path)


def _is_game_root(path: Path) -> bool:
    return (path / "data" / "Items.json").is_file() and (path / "js" / "libs" / "lz-string.js").is_file()


def _scan_for_game_roots(root: Path, max_depth: int = 8, limit: int = 20) -> list[Path]:
    if not root.is_dir():
        return []
    results: list[Path] = []
    root_depth = len(root.parts)
    for current, dirs, _files in os.walk(root):
        path = Path(current)
        depth = len(path.parts) - root_depth
        if depth > max_depth:
            dirs[:] = []
            continue
        if path.name == "www" and _is_game_root(path):
            results.append(path.resolve())
            if len(results) >= limit:
                break
    return results


def discover_game_roots(config) -> list[Path]:
    candidates = [
        config.game_root,
        Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common" / "Fear & Hunger" / "www",
        Path.home() / "pendrive" / "@home" / "kim" / ".local" / "share" / "Steam" / "steamapps" / "common" / "Fear & Hunger" / "www",
    ]
    for root in (Path.home() / "pendrive", Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common"):
        candidates.extend(_scan_for_game_roots(root))
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique and _is_game_root(resolved):
            unique.append(resolved)
    return unique


def _auto_config(config, local_env_path: Path) -> int:
    roots = discover_game_roots(config)
    if not roots:
        print("\nNao encontrei o jogo automaticamente.")
        print("Se ele esta no pendrive, confirme que o pendrive esta montado em /home/kim/pendrive.")
        if _confirm("Quer informar o caminho manualmente agora?"):
            return _manual_config(config, local_env_path)
        return 2
    if len(roots) == 1:
        chosen = roots[0]
    else:
        choices = [(str(path), str(index)) for index, path in enumerate(roots)] + [("Voltar", "exit")]
        selected = _menu("Encontrei estes jogos. Qual usar?", choices)
        if selected == "exit":
            return 130
        chosen = roots[int(selected)]
    print(f"\nJogo encontrado: {chosen}")
    if not _confirm("Salvar essa configuracao?"):
        return 130
    return _save_config(
        config,
        local_env_path,
        game_root=chosen,
        save_dir=chosen / "save",
        data_dir=chosen / "data",
        backup_dir=config.backup_dir,
    )


def _reload_config_from_file(local_env_path: Path):
    from fh_admin_tui.cli_config import load_local_env_file, merge_local_env
    from fh_admin_tui.config import AppConfig

    return AppConfig.from_env(merge_local_env(os.environ, load_local_env_file(local_env_path)))


def _show_current_config(config) -> None:
    print("\nConfiguracao atual")
    print(f"  Game root : {config.game_root}")
    print(f"  Save dir  : {config.save_dir}")
    print(f"  Data dir  : {config.data_dir}")
    print(f"  Codec     : {config.codec_script}")
    print(f"  Backups   : {config.backup_dir}")


def run_setup_menu(config, local_env_path: Path) -> str:
    from fh_admin_tui.doctor import format_report, run_diagnostics

    _print_setup_intro()
    while True:
        action = _menu(
            "O que voce quer fazer?",
            [
                ("Detectar jogo automaticamente", "detect"),
                ("Informar caminho manualmente", "manual"),
                ("Ver configuracao atual", "show"),
                ("Rodar diagnostico", "doctor"),
                ("Abrir editor", "open"),
                ("Sair", "exit"),
            ],
        )
        if action == "detect":
            if _auto_config(config, local_env_path) == 0:
                config = _reload_config_from_file(local_env_path)
        elif action == "manual":
            if _manual_config(config, local_env_path) == 0:
                config = _reload_config_from_file(local_env_path)
        elif action == "show":
            _show_current_config(config)
        elif action == "doctor":
            print(format_report(run_diagnostics(config)))
        elif action == "open":
            return "open"
        elif action == "exit":
            return "exit"


def main() -> int:
    maybe_reexec_venv()
    args = parse_args(sys.argv[1:])
    try:
        from fh_admin_tui.cli_config import LOCAL_ENV_FILE, load_local_env_file, merge_local_env
        from fh_admin_tui.config import AppConfig
        from fh_admin_tui.diagnostics import configure_logging, get_logger
        from fh_admin_tui.doctor import format_report, run_diagnostics

        log_path = configure_logging()
        logger = get_logger("launcher")
        local_env_path = Path(__file__).resolve().parent / LOCAL_ENV_FILE
        env = merge_local_env(os.environ, load_local_env_file(local_env_path))
        config = AppConfig.from_env(env).with_overrides(
            game_root=args.game_root,
            save_dir=args.save_dir,
            data_dir=args.data_dir,
            codec_script=args.codec_script,
            backup_dir=args.backup_dir,
        )
        if args.command == "configure":
            return run_configure(config, local_env_path)
        if args.command == "setup":
            setup_result = run_setup_menu(config, local_env_path)
            if setup_result != "open":
                return 0
            env = merge_local_env(os.environ, load_local_env_file(local_env_path))
            config = AppConfig.from_env(env).with_overrides(
                game_root=args.game_root,
                save_dir=args.save_dir,
                data_dir=args.data_dir,
                codec_script=args.codec_script,
                backup_dir=args.backup_dir,
            )
        report = run_diagnostics(config)
        if args.command == "doctor":
            print(format_report(report))
            return 0 if report.ok else 2
        if not report.ok:
            print(format_report(report), file=sys.stderr)
            print("\nCorrija com: ./run.py configure", file=sys.stderr)
            print("Ou rode: ./run.py doctor --game-root '/caminho/para/Fear & Hunger/www'", file=sys.stderr)
            return 2

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
