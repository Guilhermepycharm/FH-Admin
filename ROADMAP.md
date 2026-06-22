# Plano De Evolução Do FH Admin TUI

Este plano organiza as próximas melhorias sem reescrever o projeto do zero. A prioridade é aumentar segurança, testabilidade e clareza para quem clonar o repositório.

## Princípios

- Preservar o fluxo seguro: backup, decode, edição, revisão, encode, validação e apply atômico.
- Não depender de save real nos testes unitários.
- Manter a UI Textual fina: eventos, renderização, seleção e chamada de controllers/services.
- Evitar abstrações grandes antes de existir dor real.
- Cada fase deve terminar com testes passando.

## Fase 1: Comando `doctor`

Objetivo: diagnosticar problemas comuns antes de abrir a TUI.

Arquivos prováveis:

- `run.py`
- `fh_admin_tui/config.py`
- `fh_admin_tui/save_ops.py`
- `tests/test_config.py`
- `tests/test_core.py`

Escopo:

- Adicionar `./run.py doctor`.
- Verificar se existem:
  - `FH_GAME_ROOT` ou default detectável;
  - `save_dir`;
  - `data_dir`;
  - `lz-string.js`;
  - codec empacotado ou `FH_CODEC_SCRIPT` customizado;
  - `node` no PATH;
  - diretório de backup gravável.
- Mostrar mensagens com ação sugerida, não só “falhou”.

Critérios de pronto:

```bash
./run.py doctor
python -m unittest discover -s tests -v
```

## Fase 2: Testes Do Codec Real

Objetivo: garantir que o `rpgsave_codec.js` empacotado funciona.

Arquivos prováveis:

- `fh_admin_tui/resources/rpgsave_codec.js`
- `tests/test_codec.py`
- `tests/fixtures/`

Escopo:

- Criar fixture controlada para decode/encode.
- Testar `node --check` no codec.
- Testar round-trip com `NodeSaveCodec` quando `node` estiver disponível.
- Pular teste com mensagem clara quando `node` não existir.

Critérios de pronto:

```bash
node --check fh_admin_tui/resources/rpgsave_codec.js
python -m unittest tests.test_codec -v
```

## Fase 3: GitHub Actions

Objetivo: todo push validar o projeto automaticamente.

Arquivo novo:

- `.github/workflows/tests.yml`

Escopo:

- Rodar em Python 3.11+.
- Instalar dependências do projeto.
- Instalar Node.js.
- Rodar:

```bash
python -m unittest discover -s tests -v
python -m py_compile fh_admin_tui/config.py fh_admin_tui/save_ops.py fh_admin_tui/textual_app.py
node --check fh_admin_tui/resources/rpgsave_codec.js
```

Critérios de pronto:

- Workflow verde no GitHub.
- README menciona o status dos testes/CI se fizer sentido.

## Fase 4: Cobertura Do Fluxo Textual Crítico

Objetivo: testar o caminho que pode mexer em save.

Arquivos prováveis:

- `tests/test_textual_flows.py`
- `tests/fixtures/helpers.py`
- `fh_admin_tui/controllers/textual_actions.py`

Escopo:

- Abrir slot fake.
- Fazer alteração staged.
- Abrir tela de revisão.
- Confirmar apply.
- Verificar backup criado.
- Verificar que restore cria backup de segurança.

Critérios de pronto:

```bash
nix-shell -p python313Packages.textual python313Packages.rich python313Packages.rapidfuzz --run 'python -m unittest tests.test_textual_flows -v'
```

## Fase 5: Separar `mutations.py`

Objetivo: diminuir o módulo e deixar domínio mais legível.

Estrutura sugerida:

```text
fh_admin_tui/domain/
  __init__.py
  inventory.py
  characters.py
  validation.py
  diff.py
  limb_rules.py
```

Movimentos sugeridos:

- `domain/inventory.py`:
  - `inventory_key`
  - `inventory_map`
  - `list_owned_entries`
  - `set_quantity`
  - `add_quantity`
- `domain/characters.py`:
  - `actor_ids`
  - `get_actor`
  - `party_actor_ids`
  - `actor_display_name`
  - `add_skill`
  - `revive_actor`
  - `cure_infections`
  - `heal_physical_conditions`
  - `equipped_armor_ids`
  - `unequip_armor`
- `domain/limb_rules.py`:
  - configs de membros;
  - restauração de membros.
- `domain/validation.py`:
  - `validate_data`.
- `domain/diff.py`:
  - `diff_summary_lines`.

Estratégia:

- Manter `mutations.py` como compat layer inicialmente.
- Migrar imports aos poucos.
- Remover compat layer só depois de testes passarem.

Critérios de pronto:

```bash
python -m unittest discover -s tests -v
```

## Fase 6: Decisão Sobre `tui.py` Legado

Objetivo: remover ambiguidade sobre a interface curses.

Opções:

1. Manter `fh_admin_tui/tui.py` como legado/deprecado.
2. Mover para `fh_admin_tui/legacy/tui.py` e deixar stub em `tui.py`.
3. Remover totalmente se não houver dependência real.

Recomendação:

- Mover para `fh_admin_tui/legacy/tui.py`.
- Manter `fh_admin_tui/tui.py` com aviso de depreciação e ponte para o legado por um ciclo.

Critérios de pronto:

```bash
python -m py_compile fh_admin_tui/tui.py fh_admin_tui/legacy/tui.py
python -m unittest discover -s tests -v
```

## Fase 7: Melhorar `scripts/install-linux.sh`

Objetivo: deixar instalação em Linux mais previsível.

Arquivo:

- `scripts/install-linux.sh`

Escopo:

- Adicionar `--help`.
- Adicionar `--no-system-deps` como alternativa a `FH_ADMIN_SKIP_SYSTEM_DEPS=1`.
- Detectar `python3`, `pip`, `venv`, `node` e `git` antes de instalar.
- Mensagens melhores para distro desconhecida.
- Evitar recriar `.venv` sem avisar.

Critérios de pronto:

```bash
bash -n scripts/install-linux.sh
./scripts/install-linux.sh --help
FH_ADMIN_SKIP_SYSTEM_DEPS=1 ./scripts/install-linux.sh
```

## Fase 8: `importlib.resources` Para O Codec

Objetivo: localizar recurso empacotado de forma robusta.

Arquivos prováveis:

- `fh_admin_tui/config.py`
- `tests/test_config.py`

Escopo:

- Avaliar trocar o acesso direto via `Path(__file__)` por `importlib.resources`.
- Garantir compatibilidade com instalação editável e wheel.

Critérios de pronto:

```bash
python -m unittest tests.test_config -v
python -m build
```

Se `python -m build` exigir dependência extra, documentar no README ou deixar para fase posterior.

## Fase 9: Tipagem Leve

Objetivo: melhorar manutenção sem travar o projeto em uma migração grande.

Escopo:

- Adicionar dataclasses/result types onde já há retorno estruturado.
- Usar `TypedDict` só para estruturas pequenas e repetidas.
- Não tentar tipar o save inteiro ainda.

Arquivos prováveis:

- `fh_admin_tui/services/results.py`
- `fh_admin_tui/domain/*.py`
- `fh_admin_tui/save_ops.py`

Critérios de pronto:

```bash
python -m unittest discover -s tests -v
python -m py_compile fh_admin_tui/*.py fh_admin_tui/services/*.py
```

## Fase 10: Polimento De GitHub

Objetivo: deixar o repositório mais convidativo.

Escopo:

- Adicionar screenshot ou GIF da TUI.
- Criar `README.en.md` se o projeto mirar usuários fora do Brasil.
- Adicionar seção “Known limitations”.
- Criar checklist de release.
- Criar tags/releases quando houver uma versão testada com save real.

Critérios de pronto:

- README explica instalação, configuração, uso, riscos e limitações em poucos minutos.
- Nenhum arquivo local/sensível entra no repo.

## Ordem Recomendada

1. Fase 1: `doctor`.
2. Fase 2: testes do codec real.
3. Fase 3: GitHub Actions.
4. Fase 4: fluxo Textual crítico.
5. Fase 5: split de `mutations.py`.
6. Fase 6: legado `tui.py`.
7. Fase 7: instalador Linux.
8. Fase 8: `importlib.resources`.
9. Fase 9: tipagem leve.
10. Fase 10: polimento GitHub.

## Checklist De Release Futuro

Antes de criar uma tag:

```bash
python -m unittest discover -s tests -v
node --check fh_admin_tui/resources/rpgsave_codec.js
PYTHONPYCACHEPREFIX=/tmp/fh-admin-tui-pycache python -m py_compile \
  fh_admin_tui/config.py \
  fh_admin_tui/save_ops.py \
  fh_admin_tui/textual_app.py
./run.py --help
./run.py doctor
```

Também verificar manualmente:

- aplicar alteração em save de teste;
- confirmar backup criado;
- confirmar restore funcional;
- confirmar README atualizado;
- confirmar que `git status --short` está limpo.
