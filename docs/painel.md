# Painel web: o escritório do orquestrador

Front em React (Vite + TypeScript) com estética de 16 bits: um escritório onde cada setor é uma sala e cada agente tem um personagem. Mostra o histórico de execuções, o inventário das CLIs e uma prévia do roteamento. **Só leitura**: o painel não executa agentes, não lê a biblioteca MCP e não aceita nada além de GET.

## Como rodar

```sh
cd web && npm install && npm run build && cd ..
python3 -m orchestrator serve            # http://127.0.0.1:8765  (--port para trocar)
```

Em desenvolvimento, `npm run dev` em `web/` sobe o Vite com proxy de `/api` para o `serve` na porta 8765.

## Setores e personagens

| Setor | Personagem | O que representa | O que mostra |
|---|---|---|---|
| Portaria | Capitão América | Portões de aprovação (`--approve`, `--approve-mcp`, `--approve-sha256`) | Quantas execuções e preparações foram liberadas |
| Direção | Nick Fury | Classificação e roteamento | Console: digite uma tarefa, escolha uma política e veja o agente/modelo escolhido, nível e risco. Não executa nada |
| Arquivo | Viúva Negra | Histórico (`history.jsonl`) | Totais gerais, taxa de sucesso, última execução |
| Setor Codex | Homem de Ferro | Codex CLI | Execuções, OK/falhas, duração média, última, modelo mais usado, versão da CLI |
| Setor Claude | Doutor Estranho | Claude Code | Idem |
| Setor Gemini | Thor | Gemini CLI | Idem |
| Oficina de patches | Hulk | `prepare` / `apply` | Preparações de patch registradas |

Estados de cada sala: **TRABALHANDO** (execução nos últimos 10 minutos), **OCIOSO**, **AUSENTE** (CLI não encontrada no PATH) e **EM SERVIÇO** (setores sem agente). Clicar numa sala filtra o registro de execuções por aquele agente e mostra a descrição do setor.

O registro no rodapé lista cada execução: data, ação (`run` ou `prepare`), agente, modelo, versão da política, duração, status (OK, ERRO n, TEMPO ESGOTADO) e id. Filtros: todos, run, prepare, falhas. Atualiza a cada 5 segundos.

## API local (GET, JSON)

| Rota | Conteúdo |
|---|---|
| `/api/history` | Últimas 500 entradas do histórico, mais recentes primeiro; linhas inválidas são ignoradas |
| `/api/doctor?probe=1` | Inventário das CLIs; com `probe=1` consulta `--version` e `--help` (cache de 5 minutos) |
| `/api/policies` | Nomes dos arquivos em `examples/policies/` |
| `/api/plan?task=...&policy=...` | Classificação e roteamento sem efeitos; a política só pode ser uma das listadas |

Arquivos estáticos vêm de `web/dist`; rotas desconhecidas caem no `index.html` e nunca saem dessa pasta. O servidor recusa escutar fora de localhost.

## Personagens

Sprites originais de 12x16 pixels desenhados para este projeto (`web/src/pixel/heroes.ts`), inspirados nos heróis da Marvel no estilo dos jogos de Super Nintendo. Os nomes dos heróis e da Marvel são marcas de seus donos; o painel é de uso pessoal e não comercial.
