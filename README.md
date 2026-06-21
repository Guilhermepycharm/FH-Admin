# Fear & Hunger Admin TUI

Painel TUI para editar saves de Fear & Hunger 1 no terminal.

A interface suportada e baseada em Textual. O modulo `fh_admin_tui/tui.py` e a
implementacao curses legada e foi mantido apenas por compatibilidade.

## O que faz

- Lista os slots em `www/save`
- Faz backup antes de aplicar alteracoes
- Faz decode do `.rpgsave` para uma copia de trabalho temporaria
- Permite inspecionar e editar:
  - itens
  - armas
  - armaduras/acessorios
  - skills
  - party
  - revive de ator
  - cura de infeccao
  - cura de sangramento, fratura e infeccoes
  - restauracao de membros para personagens com switches mapeados
  - adicao segura de membros a party atual, respeitando o limite de quatro
- Re-encode e substitui o save original so no `apply`

## Como rodar

```bash
cd /home/kim/Projetos/fh-admin-tui
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r requirements.txt
./run.py
```

O `run.py` detecta a `.venv` local e usa ela automaticamente.

## Interface

- coluna esquerda: slots, backup, restore, atualizar
- centro: tabs de resumo, itens, armas, armaduras e atores
- direita: detalhes e acoes contextuais
- rodape: atalhos principais

## Atalhos

- `Ctrl+S`: revisar e aplicar alteracoes
- `Ctrl+B`: criar backup do slot selecionado
- `Ctrl+R`: recarregar sessao do slot aberto
- `F5`: recarregar lista de slots
- `Ctrl+Q`: sair
- `?`: ajuda curta

As acoes principais ficam em botoes contextuais no painel da direita.
Durante operacoes de arquivo, os controles ficam temporariamente desabilitados
e o painel mostra a acao em andamento.

## Diagnostico

Erros aparecem como notificacao na interface e o traceback completo e gravado em:

```text
~/.local/state/fh-admin-tui/fh-admin-tui.log
```

O log usa rotacao e tambem e emitido no terminal.

## Testes

```bash
cd /home/kim/Projetos/fh-admin-tui
.venv/bin/python -m unittest discover -s tests -v
```

O teste de codec trabalha em uma copia temporaria de um slot e nao grava nos
saves originais.

## Observacoes

- O TUI le nomes diretamente de `www/data/*.json` do jogo.
- O fluxo usa o codec local de `.rpgsave` com `lz-string.js`.
- Agora usa `textual`, `rich` e `rapidfuzz`.
- O `apply` faz validacao basica e mostra uma revisao antes de gravar.
- O save final e substituido atomicamente e sempre recebe backup antes do apply.
