# Plano v2: orquestração por API com Agno

Decisão (15/11/2026): o orquestrador passa a chamar os modelos **por API**, usando o [Agno](https://docs.agno.com/sdk/introduction) como motor de agentes, times e workflows. O modo CLI atual continua disponível para uso com assinaturas, mas deixa de ser o caminho principal.

## Objetivos

1. Tarefas objetivas e repetíveis: code review de PR e análise de código com resposta em formato fixo.
2. Desenvolvimento em paralelo: várias frentes ao mesmo tempo, coordenadas.
3. Menos tokens: modelo simples para tarefa simples, modelo forte só para coordenar e decidir.
4. Agentes que se comunicam: o coordenador delega, recebe resultados e repassa contexto entre eles.
5. Ação ao final: quando uma tarefa termina, dispara uma ação (comentar na PR, salvar na biblioteca MCP, notificar).

## Por que API muda a avaliação do Agno

| Necessidade | Com CLIs | Com API + Agno |
|---|---|---|
| Modelo por tarefa | Só o que a CLI aceitar via `--model`, sem garantia | Cada agente declara seu modelo; troca por configuração |
| Comunicação entre agentes | Texto copiado de uma CLI para outra | `Team` com líder que delega e sintetiza; estado compartilhado |
| Paralelismo | Processos separados, sem coordenação | `Workflow` com `Parallel`, `Condition`, `Loop`, `Router` |
| Resposta em formato fixo | Texto livre, conferido depois | Saída estruturada validada por esquema |
| Medir tokens e custo | Indisponível ou parcial | Métricas por execução e por agente |
| Ação ao terminar | Código próprio | Última etapa do workflow ou hook pós-execução |

Conclusão: **com API, o Agno passa a ser vantajoso**. Ele entrega pronto o que o plano anterior mandava construir à mão (coordenação, paralelismo, persistência, métricas) e acrescenta o que CLIs não permitem (escolha fina de modelo e saída estruturada).

## O que muda de custo e de risco

- **Cobrança separada.** Assinaturas como Claude Pro/Max e ChatGPT Plus não cobrem uso por API. Cada provedor cobra por token, com chave própria.
- **Times gastam mais chamadas.** A documentação do Agno avisa que líder e membros fazem chamadas separadas, o que aumenta tokens e latência. A economia vem de usar modelos baratos no trabalho pesado e de reduzir contexto, não do time em si. Por isso o plano mede custo por execução desde a etapa 1.
- **Os agentes perdem as ferramentas das CLIs.** Ler arquivos, ver diff e rodar testes passa a ser ferramenta explícita, que precisamos dar e limitar.
- **Dados vão direto ao provedor**, sob os termos de API de cada um. Diffs com segredos precisam ser filtrados antes.

## Arquitetura alvo

```
Usuário (CLI ou painel)
   │  tarefa + aprovação
   ▼
Workflow Agno ──────────────────────────────────────────────┐
   │ 1. Triagem (modelo leve): classifica e estima custo    │
   │ 2. Time de execução (líder forte, membros por papel)   │  métricas, histórico
   │ 3. Verificação (esquema + revisor)                     │  (SQLite)
   │ 4. Ação final (com aprovação se tiver efeito externo)  │
   ▼                                                        ▼
Ferramentas limitadas: leitura de repo, git diff, testes,   Painel 16 bits
biblioteca MCP (prompts), Azure DevOps, GitHub
```

## Etapas

| # | Etapa | Arquivo | Status |
|---|---|---|---|
| 1 | Fundação: Agno, provedores, catálogo de modelos, custos | [01-fundacao.md](01-fundacao.md) | implementada (15/11) |
| 2 | Agentes especialistas e ferramentas | [02-agentes.md](02-agentes.md) | implementada (15/11) |
| 3 | Times e workflows: comunicação e paralelismo | [03-orquestracao.md](03-orquestracao.md) | implementada (15/11) |
| 4 | Ações ao finalizar e aprovação | [04-acoes.md](04-acoes.md) | implementada (15/11) |
| 5 | Economia de tokens | [05-economia.md](05-economia.md) | implementada (15/11) |
| 6 | Painel com postos, filas e respostas | [06-painel.md](06-painel.md) | implementada (15/11) |

## Situação (15/11/2026)

Etapas 1 a 6 implementadas e testadas com modelo simulado (64 testes). Pendências que dependem de chaves e dados reais:

- Primeira chamada real a um provedor (falta `ANTHROPIC_API_KEY` ou outra chave).
- Preços por milhão de tokens no catálogo (`examples/api/modelos.json`), hoje nulos.
- Relatório de economia da etapa 5 com as tarefas de referência: as ferramentas (`--nivel-forcado`, `custos`, `comparar`) estão prontas, a medição precisa de chamadas reais.
- Ações `abrir_pr` e `encadear` ficaram para depois; as demais do catálogo estão prontas.
- O Testador não virou um agente: os testes são executados pelo próprio orquestrador, sem modelo, o que é mais barato e confiável.

## Princípios mantidos

- Efeito externo (comentar em PR, abrir PR, aplicar patch, enviar mensagem) só com aprovação explícita.
- Conteúdo vindo de outro agente, do repositório ou do MCP é dado não confiável, nunca instrução.
- Chaves de API só por variável de ambiente ou gerenciador de segredos; nunca em arquivo versionado nem em log.
- Cada etapa termina com testes passando, docs atualizados e commit separado.

## Antes de começar (usuário)

- Criar chaves de API nos provedores que serão usados (Anthropic, Google, OpenAI) e definir um limite de gasto mensal em cada console.
- Decidir o teto de custo por execução que o orquestrador deve respeitar (sugestão inicial: US$ 0,50).
