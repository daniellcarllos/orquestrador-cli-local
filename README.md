# Orquestrador CLI local

Protótipo Python de orquestração **single**: recebe uma tarefa, classifica, escolhe **uma** CLI de agente já instalada e autenticada pelo usuário (Codex, Claude Code ou Gemini CLI) e a executa com aprovação explícita. Opcionalmente busca prompts e contextos na biblioteca MCP (`mcp-prompts`) para montar revisões de código.

Sem chaves de API, sem dependências de runtime (biblioteca padrão do Python 3.10+), sem serviço web e sem modo team.

## Início rápido

```sh
python3 -m orchestrator doctor --probe                      # inventário das CLIs e suas opções
python3 -m orchestrator plan "Revisar este código" --cwd .   # só descreve a seleção
python3 -m orchestrator plan "Planejar uma funcionalidade" --policy examples/policies/policy.claude.example.json --cwd .
python3 -m orchestrator run "Revisar este código" --agent codex --cwd . --approve
python3 -m orchestrator prepare "Propor alteração" --cwd /caminho/projeto --output /caminho/proposta --approve
python3 -m orchestrator apply /caminho/proposta --cwd /caminho/projeto --approve-sha256 HASH_REVISADO
python3 -m orchestrator history
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

## Estrutura do projeto

```
orchestrator/
  cli.py            comandos e fluxo de aprovação
  core.py           classificação, política de roteamento e execução restrita da CLI
  capabilities.py   inventário das opções declaradas por cada CLI
  changes.py        cópia temporária, exportação e aplicação de patches
  mcp_prompts.py    leitura explícita e somente de leitura da biblioteca MCP
tests/              testes unitários (unittest, sem invocar CLIs reais)
examples/policies/  políticas de roteamento de exemplo
docs/               documentação detalhada
```

## Documentação

- [Roteamento e políticas](docs/roteamento.md): classificador, níveis, arquivo de política, exemplo para Claude Code.
- [Revisão com prompts do MCP](docs/mcp.md): variáveis `MCP_PROMPTS_URL` e `MCP_PROMPTS_TOKEN`, seleção por ID e por tag, limites.
- [Limites de segurança](docs/seguranca.md): modos de execução, isolamento, patches, histórico.
- [Evolução](docs/roadmap.md): próximos passos.

## Integração com o servidor `mcp-prompts`

A biblioteca fica em `https://code.danielcarlos.dev/mcp`. Use uma chave de **leitura**, restrita ao grupo necessário, via `MCP_PROMPTS_TOKEN`; nunca a coloque na URL nem neste repositório.

```sh
export MCP_PROMPTS_URL=https://code.danielcarlos.dev/mcp
export MCP_PROMPTS_TOKEN=...   # de um gerenciador de segredos, não do histórico do shell
python3 -m orchestrator mcp-list --project "Code Review" --group "rodo next" --approve-mcp
```

A integração usa o SDK MCP Python 2.3.x como dependência opcional: `python3 -m pip install '.[mcp]'` em um ambiente autorizado.
