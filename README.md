# Orquestrador CLI local

Orquestrador de agentes de IA com dois modos:

- **Por API (Agno):** uma equipe de agentes especialistas (triagem, análise, revisão, planejamento, implementação, coordenação), cada um com o modelo do nível certo, trabalhando em paralelo em code review, análise de código e desenvolvimento. Mede tokens e custo, respeita um teto de gasto e executa ações ao terminar, como comentar na PR. Veja [docs/guias/api.md](docs/guias/api.md).
- **Por CLI:** uma CLI já autenticada pelo usuário (Codex, Claude Code ou Gemini CLI), sem chave de API e sem dependências de runtime.

Nos dois modos, nada executa sem aprovação explícita. Opcionalmente, os agentes usam prompts e contextos da biblioteca MCP (`mcp-prompts`).

## Início rápido

```sh
python3 -m orchestrator doctor --probe                      # inventário das CLIs e suas opções
python3 -m orchestrator plan "Revisar este código" --cwd .   # só descreve a seleção
python3 -m orchestrator plan "Planejar uma funcionalidade" --policy examples/policies/policy.claude.example.json --cwd .
python3 -m orchestrator run "Revisar este código" --agent codex --cwd . --approve
python3 -m orchestrator prepare "Propor alteração" --cwd /caminho/projeto --output /caminho/proposta --approve
python3 -m orchestrator apply /caminho/proposta --cwd /caminho/projeto --approve-sha256 HASH_REVISADO
python3 -m orchestrator history
python3 -m orchestrator serve                                 # painel web local (abra o endereço com #token=...)
python3 -m unittest discover -s tests -v
```

`run` e `prepare` exigem `--approve`, que autoriza a execução e o consumo de cota da CLI selecionada. Sem isso, só apresentam o plano. A ordem padrão é Codex, Claude, Gemini; `--agent` substitui a escolha. Detectar uma CLI no PATH não comprova que esteja autenticada ou que a versão aceite as flags.

## Comandos

| Comando | O que faz | Efeitos |
|---|---|---|
| `doctor [--probe]` | Detecta CLIs no PATH; com `--probe`, consulta versão e ajuda | Só execuções locais de `--help` |
| `plan` | Classifica a tarefa e escolhe agente/modelo pela política | Nenhum |
| `run` | Executa a CLI em modo somente leitura (análise, revisão) | Consome cota; exige `--approve` |
| `prepare` | Deixa Codex ou Claude editar uma **cópia** do repositório e exporta um patch | Consome cota; nada muda na origem |
| `apply` | Aplica um patch revisado, conferindo hash e commit base | Altera o repositório |
| `mcp-list` | Lista metadados da biblioteca MCP por projeto, grupo e tag | Leitura remota; exige `--approve-mcp` |
| `history` | Mostra o histórico local de execuções (só metadados) | Nenhum |
| `serve` | Painel web local: dispara e acompanha execuções, configurações e escritório em pixel art | Escuta em 127.0.0.1 com token; execuções pedem confirmação |
| `revisar`, `analisar`, `desenvolver`, `equipe` | Fluxos da equipe por API (extra `[api]`) | Consomem tokens; exigem `--approve`; teto de gasto |
| `custos`, `comparar`, `acao`, `api-doctor`, `limpar` | Gasto, comparação, ações sobre resultados, diagnóstico | Ações externas pedem aprovação |

## Estrutura do projeto

```
orchestrator/
  cli.py              ponto de entrada: todos os comandos
  changes.py          cópia temporária, exportação e aplicação de patches (usado pelos dois modos)
  mcp_prompts.py      leitura e escrita na biblioteca MCP (usado pelos dois modos)
  terminal/           modo terminal: roteamento por política e execução restrita da CLI (core, capabilities)
  api/                modo API (Agno): catálogo, custos, ferramentas, agentes, fluxos, equipe, ações, comandos
  painel/             painel web: servidor com token (web.py) e execuções disparadas pela interface (jobs.py)
web/                  front React do painel (src/telas, src/office, src/pixel, src/panels)
tests/                testes unittest, sem rede e sem CLIs reais (modelo simulado no modo API)
examples/api/         catálogo de modelos por nível
examples/policies/    políticas de roteamento do modo terminal
docs/                 guias, segurança e plano (índice em docs/README.md)
```

## Painel web: como usar

O jeito principal de usar o orquestrador é pelo painel. Tudo roda na sua máquina:

```sh
# primeira vez
uv venv .venv && uv pip install --python .venv/bin/python -e '.[api]'
cd web && npm install && npm run build && cd ..

# chaves de API: preencha o .env (criado a partir do .env.example, permissão 600)
cp -n .env.example .env && chmod 600 .env

# sempre
.venv/bin/python -m orchestrator serve
# abra o endereço exibido, que termina com #token=...
```

| Aba | Para que serve |
|---|---|
| Nova tarefa | Escolher o fluxo (revisar, analisar, desenvolver, equipe ou terminal), o repositório, os detalhes, o teto de gasto e as ações ao terminar. **Ver plano** mostra papéis e modelos sem custo; **Executar** pede confirmação. |
| Execuções | Acompanhar cada agente ao vivo, cancelar, ler o resultado, aplicar patches e enviar a revisão para a PR, sempre com confirmação. |
| Escritório | Visão geral em pixel art: um posto por papel com modelo, chamadas, tokens e custo. |
| Configurações | Ver quais provedores têm chave, trocar o modelo de cada nível, preencher preços, padrões de teto e repositórios favoritos. |
| Como usar | Guia rápido e qual fluxo escolher. |

Como funciona por dentro: o servidor (`orchestrator/painel/web.py`, só biblioteca padrão) escuta em 127.0.0.1, exige o token gerado a cada inicialização e roda o próprio CLI em segundo plano para cada execução (`orchestrator/painel/jobs.py`). O front React fica em `web/` e é compilado em `web/dist`. Para desenvolver o front com recarga automática: `cd web && npm run dev`, com o `serve` rodando na porta 8765. Detalhes em [docs/guias/painel.md](docs/guias/painel.md).

## Documentação

Índice completo em [docs/README.md](docs/README.md).


- [Roteamento e políticas](docs/guias/terminal-roteamento.md): classificador, níveis, arquivo de política, exemplo para Claude Code.
- [Revisão com prompts do MCP](docs/guias/mcp.md): variáveis `MCP_PROMPTS_URL` e `MCP_PROMPTS_TOKEN`, seleção por ID e por tag, limites.
- [Limites de segurança](docs/seguranca.md): modos de execução, isolamento, patches, histórico.
- [Orquestração por API](docs/guias/api.md): instalação, catálogo de modelos, fluxos, ações e custos.
- [Painel web](docs/guias/painel.md): o escritório em pixel art, o que mostra e como rodar.
- [Plano v2: orquestração por API com Agno](docs/plano/README.md): objetivos, arquitetura e seis etapas.

## Integração com o servidor `mcp-prompts`

A biblioteca fica em `https://code.danielcarlos.dev/mcp`. Use uma chave de **leitura**, restrita ao grupo necessário, via `MCP_PROMPTS_TOKEN`; nunca a coloque na URL nem neste repositório.

```sh
export MCP_PROMPTS_URL=https://code.danielcarlos.dev/mcp
export MCP_PROMPTS_TOKEN=...   # de um gerenciador de segredos, não do histórico do shell
python3 -m orchestrator mcp-list --project "Code Review" --group "rodo next" --approve-mcp
```

A integração usa o SDK MCP Python 2.3.x como dependência opcional: `python3 -m pip install '.[mcp]'` em um ambiente autorizado.
