#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

run() {
  printf '==> %s\n' "$*"
  "$@"
}

install_system_deps() {
  if [ "${FH_ADMIN_SKIP_SYSTEM_DEPS:-0}" = "1" ]; then
    echo "Pulando dependencias de sistema por FH_ADMIN_SKIP_SYSTEM_DEPS=1"
    return
  fi

  if [ ! -r /etc/os-release ]; then
    echo "Nao consegui detectar a distro. Instale python3, venv/pip, git e nodejs manualmente."
    return
  fi

  . /etc/os-release
  distro="${ID:-} ${ID_LIKE:-}"

  case "$distro" in
    *ubuntu*|*debian*)
      run $SUDO apt-get update
      run $SUDO apt-get install -y python3 python3-venv python3-pip git nodejs
      ;;
    *fedora*|*rhel*)
      run $SUDO dnf install -y python3 python3-pip git nodejs
      ;;
    *arch*|*artix*)
      run $SUDO pacman -Sy --needed python python-pip git nodejs
      ;;
    *suse*|*opensuse*)
      run $SUDO zypper install -y python3 python3-pip git nodejs
      ;;
    *gentoo*)
      run $SUDO emerge --ask=n dev-lang/python dev-python/pip dev-vcs/git net-libs/nodejs
      ;;
    *)
      echo "Distro nao mapeada: ${PRETTY_NAME:-desconhecida}"
      echo "Instale python3, venv/pip, git e nodejs manualmente, ou ajuste este script."
      ;;
  esac
}

install_project() {
  cd "$ROOT_DIR"
  run python3 -m venv .venv
  run .venv/bin/python -m ensurepip --upgrade
  run .venv/bin/python -m pip install --upgrade pip
  run .venv/bin/python -m pip install -e '.[dev]'
}

install_system_deps
install_project

cat <<'MSG'

Instalacao concluida.

Para rodar:
  ./run.py

Se o jogo estiver em outro lugar, configure:
  ./run.py --game-root "/caminho/para/Fear & Hunger/www"
MSG
