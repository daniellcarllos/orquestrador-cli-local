# Painel web: o escritório do orquestrador

Front em React (Vite + TypeScript) com estética de 16 bits: um escritório onde cada setor é uma sala e cada agente tem um personagem. Mostra o histórico de execuções, o inventário das CLIs e uma prévia do roteamento. **Só leitura**: o painel não executa agentes, não lê a biblioteca MCP e não aceita nada além de GET.

## Como rodar

```sh
cd web && npm install && npm run build && cd ..
python3 -m orchestrator serve            # http://127.0.0.1:8765  (--port para trocar)
```

Em desenvolvimento, `npm run dev` em `web/` sobe o Vite com proxy de `/api` para o `serve` na porta 8765.

## Postos e personagens

Todos os personagens e objetos são originais, desenhados para este projeto (`web/src/pixel/personagens.ts`).

| Posto | Personagem | O que mostra |
|---|---|---|
| Portaria | Guarda | Portões de aprovação: execuções liberadas, ações externas, teto de gasto |
| Coordenação | Coordenadora | Etapas do coordenador e do líder do time (nível forte) |
| Triagem | Recepcionista | Classificações de tarefa (nível leve) |
| Planejamento | Arquiteta | Planos de desenvolvimento (nível forte) |
| Análise | Cartógrafa | Análises por área (nível médio) |
| Revisão | Inspetora | Revisores de segurança, bugs e qualidade (nível médio) |
| Oficina | Engenheiro | Implementações em cópia isolada (nível médio) |
| Arquivo | Arquivista | Totais de todas as execuções, com tokens e custo |
| Sala dos terminais | Operadora de terminais | Execuções das CLIs por assinatura e console de roteamento |

Cada posto da equipe de API mostra o nível e o modelo do catálogo, chamadas, sucesso, tokens, custo, duração média e o modelo mais usado. Estados: **TRABALHANDO** (atividade nos últimos 10 minutos), **OCIOSO**, **FORA DO AR** (sem chave de API e sem histórico, ou nenhuma CLI instalada) e **EM SERVIÇO**.

Clicar num posto filtra o registro pelas execuções que passaram por ele. No registro, execuções por API abrem uma linha do tempo com cada etapa: personagem, papel, rodada, nível, modelo, tokens de entrada e saída, custo, duração e status.

## API local (GET, JSON)

| Rota | Conteúdo |
|---|---|
| `/api/history` | Últimas 500 entradas do histórico, mais recentes primeiro; linhas inválidas são ignoradas |
| `/api/doctor?probe=1` | Inventário das CLIs; com `probe=1` consulta `--version` e `--help` (cache de 5 minutos) |
| `/api/policies` | Nomes dos arquivos em `examples/policies/` |
| `/api/catalogo` | Níveis e modelos do catálogo de API e quais provedores têm chave (só sim ou não) |
| `/api/plan?task=...&policy=...` | Classificação e roteamento sem efeitos; a política só pode ser uma das listadas |

Arquivos estáticos vêm de `web/dist`; rotas desconhecidas caem no `index.html` e nunca saem dessa pasta. O servidor recusa escutar fora de localhost.

