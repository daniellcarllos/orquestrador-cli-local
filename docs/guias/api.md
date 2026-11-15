# Orquestração por API (Agno)

Equipe de agentes especialistas chamados por API, cada um com modelo do nível adequado: leve para triagem, médio para análise, revisão e implementação, forte só para planejar e coordenar. O motor de workflow e o time vêm do [Agno](https://docs.agno.com/sdk/introduction). O modo CLI (assinaturas) continua disponível e não depende de nada disso.

## Instalação

```sh
uv venv .venv && uv pip install --python .venv/bin/python -e '.[api]'
.venv/bin/python -m orchestrator api-doctor          # provedores configurados (sem mostrar chaves)
```

Chaves só pelo ambiente: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`. Defina limite de gasto no console de cada provedor.

## Catálogo de modelos

`examples/api/modelos.json` define o modelo de cada nível, alternativos de outros provedores e preços por milhão de tokens. **Preencha os preços** com a tabela oficial de cada provedor: sem preço, o custo em dólares não é calculado nem limitado (o teto de tokens continua valendo). Use `--catalogo outro.json` para trocar.

| Papel | Nível | Faz |
|---|---|---|
| triagem | leve | Classifica tipo, complexidade, risco e áreas |
| analista | médio | Mapeia uma área do código (com ferramentas de leitura) |
| revisor | médio | Revisa o diff com um foco; segurança sobe para forte quando o risco é alto |
| implementador | médio | Implementa uma subtarefa nos arquivos permitidos |
| planejador | forte | Divide o objetivo em subtarefas independentes |
| coordenador | forte | Consolida, prioriza e decide; lidera o modo equipe |

## Comandos

Todos mostram o plano (papéis, modelos, teto) e só executam com `--approve`. `--simulado` usa um modelo falso: sem chave, sem custo, útil para testar o fluxo.

```sh
# code review: triagem → 3 revisores em paralelo (segurança, bugs, qualidade) → consolidação
orchestrator revisar --cwd repo --base main --approve
orchestrator revisar --diff pr.diff --mcp-prompt-id 93d6961d2a --mcp-project "Code Review" --mcp-group "rodo next" --approve

# análise: triagem escolhe as áreas → um analista por área em paralelo → consolidação
orchestrator analisar "Como funciona a autenticação?" --cwd repo --approve

# desenvolvimento em paralelo: plano → implementadores em cópias isoladas → testes → revisão
# (até 2 rodadas de ajuste) → consolidação. Gera um patch por subtarefa; nada muda na origem.
orchestrator desenvolver "Adicionar validação de CPF no cadastro" --cwd repo --teste "dotnet test" --approve

# tarefa aberta com o Team do Agno: líder forte delega para analista, revisor e planejador
orchestrator equipe "Proponha uma estratégia de cache para o módulo X" --cwd repo --approve

orchestrator custos --dias 7            # gasto e tokens por fluxo e por modelo
orchestrator comparar ID_A ID_B         # custo/tokens/tempo de duas execuções
orchestrator limpar --dias 30           # remove pastas de execução antigas
```

Opções comuns: `--teto-usd` (padrão 0,50 ou `ORCHESTRATOR_TETO_USD`), `--teto-tokens`, `--teto-dia-usd`, `--nivel-forcado forte` (para comparar custo), `--json`.

## Ações ao finalizar

```sh
orchestrator revisar --cwd repo --base main --approve \
  --ao-finalizar notificar \
  --ao-finalizar "comentar_pr_azure:org=minhaorg,projeto=Proj,repo=api,pr=123"
```

| Ação | Aprovação | Requisitos |
|---|---|---|
| `notificar` | automática | macOS: notificação; outros: aviso no terminal |
| `comentar_pr_azure` | `SIM` no terminal ou `--aprovar-acoes comentar_pr_azure` | `AZURE_DEVOPS_PAT` |
| `comentar_pr_github` | idem | `GITHUB_TOKEN`; `repo=dono/nome,pr=N` |
| `salvar_na_biblioteca` | idem | `MCP_PROMPTS_URL`, `MCP_PROMPTS_TOKEN` com escrita; `titulo=...,projeto=...` |

O texto enviado é o mesmo que foi aprovado (conferido por SHA-256) e passa pela redação de segredos. Sem aprovação, a ação fica pendente e pode ser repetida: `orchestrator acao ID comentar_pr_azure:... --aprovar-acoes comentar_pr_azure`.

## O que fica registrado

- `~/.local/state/orquestrador-cli-local/execucoes/<id>/`: `resultado.md`, `resultado.json`, `meta.json` e, no desenvolvimento, uma pasta de proposta por subtarefa e rodada (aplique com `orchestrator apply`). Arquivos com permissão 600.
- `history.jsonl`: uma linha por execução com fluxo, status, duração, custo, tokens e etapas (papel, nível, modelo, tokens, custo, status). Sem o texto da tarefa.

## Segurança

- Agentes não têm shell: só listar, ler e buscar dentro do repositório, sem seguir links, sem `.env`, chaves, binários ou `appsettings.*.json`.
- Diffs e arquivos passam por redação de segredos antes de ir ao modelo. Conteúdo de código, documentos e respostas de outros agentes vai marcado como dado não confiável.
- Testes rodam numa cópia temporária, só com o comando informado em `--teste`, sem shell.
- Falha de formato, teto atingido ou erro do provedor param o fluxo na hora: não há novas tentativas pagas fora de controle (uma única correção de formato por etapa, feita pelo Agno).
- Os dados vão ao provedor sob os termos de API dele.
