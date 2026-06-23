# Fear & Hunger Admin TUI

Editor TUI para saves de **Fear & Hunger 1**, feito em Python com Textual. O app abre os saves em uma cópia temporária, mostra as alterações para revisão, cria backup automático e só grava no save original depois de validar o resultado.

## Status

Projeto em desenvolvimento. Já possui fixtures falsas, testes unitários, testes de fluxo Textual e validações antes de gravar, mas ainda é um editor de save: mantenha cópias externas dos saves importantes.

A interface principal suportada é a Textual. A antiga interface curses foi movida para `fh_admin_tui/legacy/tui.py` e fica fora do caminho principal.

## Recursos

- Lista slots `file*.rpgsave` em `www/save`.
- Decodifica o save para uma cópia temporária de trabalho.
- Edita itens, armas, armaduras, skills, party, revive, infecções, ferimentos e membros ausentes mapeados.
- Mostra revisão antes do apply.
- Cria backup automático antes de aplicar alterações.
- Cria backup de segurança antes de restaurar outro backup.
- Valida estrutura do save, codec, catálogo do jogo e round-trip antes de gravar.
- Permite configurar caminhos por setup interativo, arquivo local, variáveis de ambiente ou argumentos CLI.

## Instalação

Clone e instale:

```bash
git clone https://github.com/Guilhermepycharm/FH-Admin.git fh-admin-tui
cd fh-admin-tui
./scripts/install-linux.sh
```

O instalador cobre Ubuntu/Debian, Fedora/RHEL, Arch/Artix, openSUSE/SUSE e Gentoo. Ele também cria atalhos em `~/.local/bin`:

```bash
fh-admin-tui
fh admin tui
```

Se você já tem Python, pip/venv, git e Node.js instalados, pule dependências de sistema:

```bash
./scripts/install-linux.sh --no-system-deps
```

Em NixOS, esse modo é o recomendado. O instalador cria a `.venv`, instala o projeto em modo editável e adiciona `~/.local/bin` ao Fish via `~/.config/fish/conf.d/fh-admin-tui.fish` quando necessário.

Instalação manual equivalente:

```bash
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -e '.[dev]'
```

## Primeiro Uso

Depois de instalar, abra um terminal novo e rode:

```bash
fh admin tui setup
```

Ou, dentro do checkout:

```bash
./run.py setup
```

O setup abre um menu interativo:

```text
1. Detectar jogo automaticamente
2. Informar caminho manualmente
3. Ver configuracao atual
4. Rodar diagnostico
5. Abrir editor
6. Sair
```

Se o jogo estiver no pendrive, você pode informar a pasta `www` assim:

```text
$HOME/pendrive/@home/<usuario>/.local/share/Steam/steamapps/common/Fear & Hunger/www
```

Também pode digitar relativo ao seu home:

```text
pendrive/@home/<usuario>/.local/share/Steam/steamapps/common/Fear & Hunger/www
```

Troque `<usuario>` pelo nome do usuario copiado no pendrive. O setup aceita caminhos com espacos, aspas ou barras invertidas e salva tudo em `.fh-admin-tui.env`, ignorado pelo Git.

## Como Executar

Abrir o editor:

```bash
fh admin tui
```

ou:

```bash
fh-admin-tui
```

Rodar diagnóstico:

```bash
fh admin tui doctor
```

Reabrir o setup:

```bash
fh admin tui setup
```

Comandos diretos pelo checkout continuam funcionando:

```bash
./run.py
./run.py doctor
./run.py setup
./run.py configure
```

`configure` é o caminho manual direto; `setup` é o menu interativo recomendado.

## Configuração

Ordem de prioridade dos caminhos:

1. argumentos CLI, como `--game-root`;
2. variáveis de ambiente;
3. `.fh-admin-tui.env` criado pelo setup;
4. defaults do projeto.

Variáveis aceitas:

- `FH_GAME_ROOT`: pasta `www` do jogo.
- `FH_SAVE_DIR`: pasta de saves; se omitida, usa `$FH_GAME_ROOT/save`.
- `FH_DATA_DIR`: pasta de dados; se omitida, usa `$FH_GAME_ROOT/data`.
- `FH_CODEC_SCRIPT`: caminho para `rpgsave_codec.js`; normalmente não precisa configurar.
- `FH_BACKUP_DIR`: pasta de backups automáticos.

Exemplo:

```bash
FH_GAME_ROOT="$HOME/pendrive/@home/<usuario>/.local/share/Steam/steamapps/common/Fear & Hunger/www" fh admin tui doctor
```

## Como Usar A TUI

A tela principal é dividida em três áreas:

- esquerda: slots, backup, restauração e atualização da lista;
- centro: abas de resumo, itens, armas, armaduras e personagens;
- direita: detalhes da seleção atual e ações contextuais.

Atalhos principais:

- `Ctrl+S`: revisar e aplicar alterações;
- `Ctrl+B`: criar backup do slot selecionado;
- `Ctrl+R`: recarregar a sessão do slot aberto;
- `F5`: recarregar lista de slots;
- `Ctrl+Q`: sair;
- `?`: ajuda curta.

## Uninstall

Para remover os atalhos de usuário criados pelo instalador:

```bash
./scripts/uninstall-linux.sh
```

Por padrão, ele remove apenas:

- `~/.local/bin/fh`
- `~/.local/bin/fh-admin-tui`

Ele **não remove saves nem backups**. Opções extras:

```bash
./scripts/uninstall-linux.sh --config  # remove .fh-admin-tui.env
./scripts/uninstall-linux.sh --venv    # remove .venv
```

## Estrutura Do Projeto

- `run.py`: launcher, setup CLI, diagnóstico e ponte para a TUI.
- `fh_admin_tui/config.py`: resolução de paths, env vars e defaults.
- `fh_admin_tui/cli_config.py`: leitura/escrita da config local `.fh-admin-tui.env`.
- `fh_admin_tui/doctor.py`: diagnóstico de runtime, paths, Node, catálogo e backups.
- `fh_admin_tui/domain/`: regras testáveis de inventário, personagens, validação e resumo de alterações.
- `fh_admin_tui/mutations.py`: fachada de compatibilidade para imports antigos.
- `fh_admin_tui/save_ops.py`: IO, backup, codec, sessão de edição e escrita atômica.
- `fh_admin_tui/textual_app.py`: shell principal Textual.
- `fh_admin_tui/controllers/`: fluxos Textual e chamadas de serviços.
- `fh_admin_tui/services/`: casos de uso de inventário, personagens e revisão antes do apply.
- `fh_admin_tui/ui/`: layout, telas/modais e helpers de renderização.
- `fh_admin_tui/legacy/tui.py`: interface curses legada.
- `scripts/install-linux.sh`: instalador Linux e atalhos de usuário.
- `scripts/uninstall-linux.sh`: remoção segura dos atalhos.
- `tests/fixtures/`: saves e catálogos mínimos falsos.

## Desenvolvimento

Rodar testes:

```bash
python -m unittest discover -s tests -v
```

Checar sintaxe dos módulos principais:

```bash
PYTHONPYCACHEPREFIX=/tmp/fh-admin-tui-pycache python -m py_compile \
  run.py \
  fh_admin_tui/config.py \
  fh_admin_tui/cli_config.py \
  fh_admin_tui/doctor.py \
  fh_admin_tui/save_ops.py \
  fh_admin_tui/domain/inventory_rules.py \
  fh_admin_tui/domain/character_rules.py \
  fh_admin_tui/domain/save_validation.py \
  fh_admin_tui/domain/change_summary.py \
  fh_admin_tui/services/results.py \
  fh_admin_tui/services/actor_service.py \
  fh_admin_tui/services/inventory_service.py \
  fh_admin_tui/services/review_service.py \
  fh_admin_tui/controllers/textual_actions.py \
  fh_admin_tui/ui/screens.py \
  fh_admin_tui/ui/rendering.py \
  fh_admin_tui/ui/layout.py \
  fh_admin_tui/textual_app.py \
  fh_admin_tui/legacy/tui.py
```

Validar o codec empacotado:

```bash
node --check fh_admin_tui/resources/rpgsave_codec.js
```

O GitHub Actions roda testes, compile check e `node --check`.

## Cobertura De Testes

A suíte usa `unittest` e fixtures falsas, então não depende do jogo instalado. Cobertura atual:

- configuração por env vars, arquivo local e defaults;
- setup/diagnóstico de caminhos;
- codec empacotado e round-trip controlado;
- mutações de inventário e personagens;
- validação de saves malformados;
- backup/apply sem tocar em save real;
- proteção contra codec que altera dados staged;
- restore recusando backup inválido;
- fluxo Textual básico e apply com backup quando `textual` está instalado.

## Troubleshooting

- `fh: command not found`: abra um terminal novo ou rode `export PATH="$HOME/.local/bin:$PATH"`.
- `Dependência ausente: textual`: rode `./scripts/install-linux.sh --no-system-deps` ou reinstale a venv.
- `Pasta de saves nao encontrada`: rode `fh admin tui setup` e confira a pasta `www` do jogo.
- `Arquivos ausentes em data`: o game root está errado; ele deve apontar para a pasta `www`, não para `Fear & Hunger` nem para `data`.
- `Arquivo de lz-string nao encontrado`: confira se `FH_GAME_ROOT` aponta para a pasta `www` correta.
- `Arquivo de script do codec nao encontrado`: reinstale o projeto; o codec vem incluso no pacote.
- Falha fatal na UI: veja `~/.local/state/fh-admin-tui/fh-admin-tui.log`.

## Aviso Sobre Saves

Este projeto edita arquivos de save. O apply cria backup automático e valida antes de gravar, mas você ainda deve manter backup externo dos saves importantes.

## Licença

Distribuído sob GPL-3.0-or-later. Veja `LICENSE`.
