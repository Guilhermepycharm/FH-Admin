# Fear & Hunger Admin TUI

Editor TUI para saves de **Fear & Hunger 1**, feito em Python com Textual. O objetivo é editar saves com mais segurança do que mexer manualmente nos arquivos: o app trabalha em cópia temporária, cria backups automáticos e só grava no save original depois de validação.

## English summary

Fear & Hunger Admin TUI is an early-stage terminal save editor for **Fear & Hunger 1**. It can inspect save slots, edit common inventory and character data, and apply changes with automatic backups. Main usage commands are documented in [Como executar](#como-executar), and configuration is controlled through CLI arguments or environment variables.

## Status

Este é um projeto em desenvolvimento. Ele já tem testes unitários, fixtures falsas e validações antes de gravar, mas ainda deve ser usado com cuidado. Faça backup dos saves antes de editar qualquer arquivo importante.

A interface principal suportada é a Textual. A interface curses em `fh_admin_tui/tui.py` é legado/deprecada e existe apenas por compatibilidade enquanto o fluxo Textual amadurece.

## Recursos

- Lista slots `file*.rpgsave` em `www/save`.
- Decodifica o save para uma cópia temporária de trabalho.
- Edita itens, armas, armaduras, skills, party, revive, infecções, ferimentos e membros ausentes mapeados.
- Cria backup antes de aplicar alterações.
- Cria backup de segurança antes de restaurar outro backup.
- Valida a estrutura básica do save antes de gravar.
- Faz encode, decodifica o resultado para validação e substitui o save original de forma atômica.
- Permite configurar paths por variáveis de ambiente ou argumentos CLI.

## Instalação

```bash
git clone https://github.com/Guilhermepycharm/FH-Admin.git fh-admin-tui
cd fh-admin-tui
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -e '.[dev]'
```

`./run.py` detecta a `.venv` local e reexecuta com ela automaticamente.

Script de instalação para Ubuntu, Fedora, Arch, openSUSE/SUSE, Gentoo e Artix:

```bash
./scripts/install-linux.sh
```

Se você já instalou as dependências de sistema e quer pular essa etapa:

```bash
FH_ADMIN_SKIP_SYSTEM_DEPS=1 ./scripts/install-linux.sh
```

Em NixOS, também dá para rodar sem instalar globalmente:

```bash
nix-shell -p python313Packages.textual python313Packages.rich python313Packages.rapidfuzz nodejs
```

## Configuração

Por padrão, o app tenta usar:

```text
~/.local/share/Steam/steamapps/common/Fear & Hunger/www
```

Variáveis aceitas:

- `FH_GAME_ROOT`: pasta `www` do jogo.
- `FH_SAVE_DIR`: pasta de saves; se omitida, usa `$FH_GAME_ROOT/save`.
- `FH_DATA_DIR`: pasta de dados; se omitida, usa `$FH_GAME_ROOT/data`.
- `FH_CODEC_SCRIPT`: caminho para `rpgsave_codec.js`.
- `FH_BACKUP_DIR`: pasta de backups automáticos.

Exemplo com variáveis de ambiente:

```bash
export FH_GAME_ROOT="$HOME/.local/share/Steam/steamapps/common/Fear & Hunger/www"
export FH_SAVE_DIR="$FH_GAME_ROOT/save"
export FH_DATA_DIR="$FH_GAME_ROOT/data"
export FH_CODEC_SCRIPT="$HOME/.local/share/fh-admin-tui/rpgsave_codec.js"
export FH_BACKUP_DIR="$HOME/fh-save-backups"
./run.py
```

Exemplo com argumentos:

```bash
./run.py \
  --game-root "$HOME/.local/share/Steam/steamapps/common/Fear & Hunger/www" \
  --codec-script "$HOME/.local/share/fh-admin-tui/rpgsave_codec.js" \
  --backup-dir "$HOME/fh-save-backups"
```

## Como executar

No checkout do projeto:

```bash
./run.py
```

Depois de instalar com `pip install -e .`, o entrypoint também fica disponível:

```bash
fh-admin-tui
```

## Como usar

A tela principal é dividida em três áreas:

- Esquerda: slots, backup, restauração e atualização da lista.
- Centro: abas de resumo, itens, armas, armaduras e personagens.
- Direita: detalhes da seleção atual e ações contextuais.

Atalhos principais:

- `Ctrl+S`: revisar e aplicar alterações.
- `Ctrl+B`: criar backup do slot selecionado.
- `Ctrl+R`: recarregar a sessão do slot aberto.
- `F5`: recarregar lista de slots.
- `Ctrl+Q`: sair.
- `?`: ajuda curta.

## Estrutura do projeto

- `fh_admin_tui/config.py`: resolução de paths, variáveis de ambiente, defaults e validação de runtime.
- `fh_admin_tui/mutations.py`: mutações e regras puras sobre a estrutura do save.
- `fh_admin_tui/save_ops.py`: IO, backup, codec, sessão de edição e escrita atômica.
- `fh_admin_tui/textual_app.py`: shell principal da aplicação Textual, eventos, seleção e renderização.
- `fh_admin_tui/controllers/`: fluxos Textual que orquestram modais, confirmações e chamadas de serviços.
- `fh_admin_tui/services/`: casos de uso de inventory, personagens e revisão antes do apply.
- `fh_admin_tui/ui/`: layout, telas/modais e helpers de renderização.
- `fh_admin_tui/tui.py`: interface curses legada/deprecada; não é o caminho principal recomendado.
- `scripts/install-linux.sh`: instalador simples para distros Linux comuns.
- `tests/fixtures/`: saves e catálogos mínimos falsos para testes sem jogo instalado.

## Desenvolvimento

Rodar testes unitários:

```bash
python -m unittest discover -s tests -v
```

Checar sintaxe dos módulos principais sem gravar `__pycache__` no repo:

```bash
PYTHONPYCACHEPREFIX=/tmp/fh-admin-tui-pycache python -m py_compile \
  fh_admin_tui/config.py \
  fh_admin_tui/save_ops.py \
  fh_admin_tui/ui/screens.py \
  fh_admin_tui/ui/rendering.py \
  fh_admin_tui/ui/layout.py \
  fh_admin_tui/services/results.py \
  fh_admin_tui/services/actor_service.py \
  fh_admin_tui/services/inventory_service.py \
  fh_admin_tui/services/review_service.py \
  fh_admin_tui/controllers/textual_actions.py \
  fh_admin_tui/textual_app.py
```

## Testes

A suíte usa `unittest` e fixtures falsas, então não depende de um save real instalado no computador do desenvolvedor.

Cobertura atual:

- configuração por env vars e defaults;
- mutações de inventory e personagens;
- validação de saves malformados;
- backup/apply sem tocar em save real;
- proteção contra round-trip de codec que altera dados staged;
- restore recusando backup inválido;
- fluxo Textual básico quando `textual` está instalado.

Em ambientes sem dependências de UI, os testes Textual são pulados explicitamente.

## Roadmap

- Aumentar cobertura dos fluxos de apply/restore via Textual.
- Melhorar mensagens de erro com sugestões de variáveis de ambiente específicas.
- Decidir se a interface curses legada será removida em uma versão futura.

## Aviso sobre saves

Este projeto edita arquivos de save. Embora o apply crie backup automático e valide antes de gravar, mantenha cópias externas dos saves importantes. Não use em saves únicos sem backup.

## Troubleshooting

- `Dependência ausente: textual`: crie a `.venv` e rode `.venv/bin/python -m pip install -e '.[dev]'`.
- `Pasta de saves nao encontrada`: configure `FH_GAME_ROOT` ou `FH_SAVE_DIR`.
- `Arquivo de script do codec nao encontrado`: configure `FH_CODEC_SCRIPT` para o `rpgsave_codec.js` correto.
- `Arquivo de lz-string nao encontrado`: confirme que `FH_GAME_ROOT` aponta para a pasta `www` do jogo.
- Falha fatal na UI: consulte `~/.local/state/fh-admin-tui/fh-admin-tui.log`.

## Licença

Distribuído sob GPL-3.0-or-later. Veja `LICENSE`.
