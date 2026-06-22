#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_SYSTEM_DEPS="${FH_ADMIN_SKIP_SYSTEM_DEPS:-0}"
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

usage() {
  cat <<'MSG'
Uso: scripts/install-linux.sh [--no-system-deps]

Instala dependencias de sistema conhecidas, cria/repara .venv e instala o projeto
em modo editavel com dependencias de desenvolvimento.

Opcoes:
  --no-system-deps   pula apt/dnf/pacman/zypper/emerge
  -h, --help         mostra esta ajuda
MSG
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-system-deps)
      SKIP_SYSTEM_DEPS=1
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

run() {
  printf '==> %s\n' "$*"
  "$@"
}

install_system_deps() {
  if [ "$SKIP_SYSTEM_DEPS" = "1" ]; then
    echo "Pulando dependencias de sistema."
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
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 nao encontrado no PATH. Instale Python 3 antes de continuar." >&2
    exit 1
  fi
  if [ -e .venv/bin/python ] && [ ! -x .venv/bin/python ]; then
    backup_name=".venv.broken.$(date +%Y%m%d%H%M%S)"
    echo "Venv local quebrada detectada; movendo .venv para $backup_name"
    run mv .venv "$backup_name"
  elif [ -L .venv/bin/python ] && [ ! -e .venv/bin/python ]; then
    backup_name=".venv.broken.$(date +%Y%m%d%H%M%S)"
    echo "Venv local com symlink quebrado detectada; movendo .venv para $backup_name"
    run mv .venv "$backup_name"
  fi
  if [ ! -x .venv/bin/python ]; then
    run python3 -m venv .venv
  fi
  run .venv/bin/python -m ensurepip --upgrade
  run .venv/bin/python -m pip install --upgrade pip
  run .venv/bin/python -m pip install -e '.[dev]'
}

install_user_commands() {
  local user_bin="${HOME}/.local/bin"
  run mkdir -p "$user_bin"

  cat > "$user_bin/fh-admin-tui" <<MSG
#!/usr/bin/env bash
exec "$ROOT_DIR/run.py" "\$@"
MSG
  chmod +x "$user_bin/fh-admin-tui"

  cat > "$user_bin/fh" <<MSG
#!/usr/bin/env bash
if [ "\${1:-}" = "admin" ] && [ "\${2:-}" = "tui" ]; then
  shift 2
  exec "$ROOT_DIR/run.py" "\$@"
fi
if [ "\${1:-}" = "admin" ]; then
  shift 1
  exec "$ROOT_DIR/run.py" "\$@"
fi
echo "Uso: fh admin tui [doctor|configure|setup]" >&2
echo "Ou:  fh-admin-tui [doctor|configure|setup]" >&2
exit 2
MSG
  chmod +x "$user_bin/fh"

  ensure_user_bin_on_path "$user_bin"
}

ensure_user_bin_on_path() {
  local user_bin="$1"
  case ":$PATH:" in
    *":$user_bin:"*)
      ;;
    *)
      local profile_line='case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac'
      touch "$HOME/.profile"
      if ! grep -F '$HOME/.local/bin' "$HOME/.profile" >/dev/null 2>&1; then
        printf '\n# FH Admin TUI user commands\n%s\n' "$profile_line" >> "$HOME/.profile"
      fi
      ;;
  esac

  if [ -n "${SHELL:-}" ] && [ "${SHELL##*/}" = "fish" ]; then
    local fish_conf="$HOME/.config/fish/conf.d/fh-admin-tui.fish"
    mkdir -p "$(dirname "$fish_conf")"
    cat > "$fish_conf" <<'MSG'
if not contains -- $HOME/.local/bin $PATH
    fish_add_path -m $HOME/.local/bin
end
MSG
  fi
}

install_system_deps
install_project
install_user_commands

cat <<'MSG'

Instalacao concluida.

Para rodar:
  ./run.py

Ou, depois de abrir um novo terminal:
  fh-admin-tui
  fh admin tui

Para diagnosticar paths e dependencias:
  ./run.py doctor

Se o jogo estiver em outro lugar, configure:
  ./run.py --game-root "/caminho/para/Fear & Hunger/www"
MSG
