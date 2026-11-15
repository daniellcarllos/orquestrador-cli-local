# Etapa 5: economia de tokens

Meta: gastar menos sem perder qualidade, e **provar** a economia com números, não com suposição.

## 5.1 Onde a economia acontece

| Técnica | Como | Efeito esperado |
|---|---|---|
| Modelo por nível | Triagem e checagens no leve, trabalho no médio, só coordenação no forte | Maior parte dos tokens passa pelos modelos baratos |
| Escalada sob demanda | Começa no médio; sobe para o forte só se a triagem marcar risco alto, o diff for grande ou a validação falhar | Forte só quando necessário |
| Contexto mínimo | Cada membro recebe só os arquivos e trechos da sua parte, não o repositório inteiro | Menos tokens de entrada |
| Estado estruturado | Etapas trocam JSON curto (achados, decisões), não textos longos | Menos tokens repassados |
| Cache de prompt | Instruções fixas de cada papel e documentos da biblioteca no início do prompt, para aproveitar o cache do provedor | Entrada repetida mais barata |
| Saída curta | Esquemas com campos objetivos e limite de tamanho | Menos tokens de saída |
| Sem conversa livre | Comunicação só via líder, workflow e estado | Evita multiplicação de chamadas |

## 5.2 Custo do próprio time

Times do Agno fazem chamadas separadas para o líder e para cada membro. Em tarefa pequena, isso pode custar **mais** que um agente só. Regra:

- Triagem decide o caminho: tarefa simples vai para um agente único, sem time.
- Time só para tarefas que a triagem classificar como médias ou grandes.

## 5.3 Medição

- Cada execução registra tokens de entrada, saída e cache, e custo por agente e por modelo.
- `orchestrator custos --periodo 7d` mostra gasto por fluxo, por agente e por modelo.
- **Linha de base**: um conjunto fixo de tarefas de referência (3 PRs para revisar, 2 módulos para analisar, 1 desenvolvimento com 2 subtarefas) rodado em dois modos:
  - tudo no modelo forte, agente único;
  - orquestrado por níveis.
- Comparar custo, tempo e qualidade (achados reais encontrados, falsos positivos, testes passando).

## Critérios de aceite

- Relatório de comparação salvo em `docs/avaliacoes/`, com custo total, custo por tarefa e qualidade de cada modo.
- Meta inicial: reduzir o custo em pelo menos 40% sem perder achados críticos nas revisões de referência. Se não atingir, ajustar os níveis antes de seguir.
