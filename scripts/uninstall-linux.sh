#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOVE_CONFIG=0
REMOVE_VENV=0

usage() {
  cat <<'MSG'
Uso: scripts/uninstall-linux.sh [--config] [--venv]

Remove os atalhos de usuario criados pelo instalador:
  ~/.local/bin/fh
  ~/.local/bin/fh-admin-tui

Por padrao nao remove saves, backups, configuracao local nem venv.

Opcoes:
  --config   remove .fh-admin-tui.env do checkout atual
  --venv     remove .venv do checkout atual
  -h, --help mostra esta ajuda
MSG
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --config)
      REMOVE_CONFIG=1
      ;;
    --venv)
      REMOVE_VENV=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Opcao desconhecida: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

remove_file() {
  local path="$1"
  if [ -e "$path" ] || [ -L "$path" ]; then
    rm -f "$path"
    echo "Removido: $path"
  else
    echo "Ja nao existe: $path"
  fi
}

remove_file "$HOME/.local/bin/fh"
remove_file "$HOME/.local/bin/fh-admin-tui"

if [ "$REMOVE_CONFIG" = "1" ]; then
  remove_file "$ROOT_DIR/.fh-admin-tui.env"
fi

if [ "$REMOVE_VENV" = "1" ]; then
  if [ -d "$ROOT_DIR/.venv" ]; then
    rm -rf "$ROOT_DIR/.venv"
    echo "Removido: $ROOT_DIR/.venv"
  else
    echo "Ja nao existe: $ROOT_DIR/.venv"
  fi
fi

cat <<'MSG'

Uninstall concluido.
Saves e backups nao foram removidos.
MSG
