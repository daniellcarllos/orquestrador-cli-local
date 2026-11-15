# Etapa 3: times e workflows (comunicação e paralelismo)

Meta: os agentes passam a trabalhar juntos. Um coordenador com modelo forte divide o trabalho, os membros com modelos mais baratos executam em paralelo, e os resultados circulam entre eles de forma controlada.

## 3.1 Como os agentes se comunicam

No Agno, a comunicação acontece pelo **time** e pelo **workflow**, não por conversa livre entre agentes:

- **Team (líder + membros):** o líder decide quem faz o quê, envia a cada membro só o necessário, recebe as respostas e sintetiza. Modos disponíveis: `coordinate` (divide e delega, padrão), `route` (manda para um especialista e devolve direto), `broadcast` (mesma tarefa para todos e síntese) e `tasks` (lista de tarefas até cumprir o objetivo).
- **Workflow:** etapas determinísticas; a saída de uma etapa é a entrada da próxima. Containers `Parallel`, `Condition`, `Loop` e `Router`.
- **Estado compartilhado da sessão:** dados estruturados (lista de arquivos, achados, decisões) que todas as etapas leem e atualizam, em vez de repassar textos longos.

Conversa livre entre agentes foi descartada de propósito: multiplica tokens e torna o resultado imprevisível.

## 3.2 Fluxos prontos

**Code review de PR**

```
Triagem (leve) ─► divide o diff por área
   └► Parallel: Revisor(segurança) | Revisor(bugs) | Revisor(estilo e testes)   (médio)
        └► Coordenador (forte): remove duplicados, prioriza, dá o veredito
             └► Ação final: revisao.md + comentário na PR (com aprovação)
```

**Análise de código**

```
Triagem (leve) ─► mapa de módulos
   └► Parallel: Analista por módulo (médio)
        └► Coordenador (forte): visão geral, riscos, recomendações
```

**Desenvolvimento em paralelo**

```
Coordenador (forte): plano com subtarefas independentes e critérios de aceite
   └► Parallel: Implementador por subtarefa (médio), cada um em cópia própria do repositório
        └► Testador por patch (leve/médio)
             └► Loop (máx. 2 rodadas): Revisor ─► "ajustar" volta ao Implementador
                  └► Coordenador: junta patches sem conflito e entrega para revisão humana
```

## 3.3 Limites

- Concorrência máxima configurável (padrão 3 agentes simultâneos).
- Rodadas de ajuste limitadas; nunca laço sem fim.
- Teto de custo vale para o fluxo inteiro, somando todas as chamadas.
- Cancelamento (Ctrl+C) interrompe todas as etapas e registra até onde chegou; `orchestrator retomar <id>` continua do ponto salvo.

## 3.4 Histórico

Persistência do Agno em SQLite local, com uma execução "mãe" e uma linha por etapa e por agente: modelo, tokens, custo, duração, status. O painel lê daí.

## Critérios de aceite

- Code review de uma PR real com três revisores em paralelo e consolidação, custo registrado por agente.
- Desenvolvimento em paralelo de duas subtarefas independentes gerando dois patches que aplicam sem conflito.
- Comparação de custo: fluxo com modelos por nível contra o mesmo fluxo todo no modelo forte (ver etapa 5).
