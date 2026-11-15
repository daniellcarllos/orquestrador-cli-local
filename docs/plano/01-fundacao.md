# Etapa 1: fundação (Agno, provedores, catálogo de modelos, custos)

Meta: o orquestrador consegue chamar qualquer modelo configurado por API, sabe quanto cada chamada custou e recusa execuções acima do teto.

## 1.1 Estrutura

```
orchestrator/
  api/
    modelos.py      catálogo: níveis → provedor + id do modelo
    custos.py       preço por token (configurável) e cálculo por execução
    segredos.py     leitura das chaves só do ambiente, com verificação
    historico.py    persistência Agno (SQLite) + exportação para o painel
  cli.py            novos comandos: tarefa, revisar, analisar, paralelo
```

O núcleo atual (modo CLI) continua sem dependências. A parte por API é um extra: `pip install '.[api]'`, que instala `agno` com os provedores escolhidos e versão fixada.

## 1.2 Catálogo de modelos por nível

Arquivo `examples/modelos.json`. Os IDs são exemplos e precisam ser conferidos na conta de cada provedor:

```json
{
  "versao": "modelos-1",
  "niveis": {
    "leve":   { "provedor": "anthropic", "modelo": "claude-haiku-5-5" },
    "medio":  { "provedor": "anthropic", "modelo": "claude-sonnet-5-5" },
    "forte":  { "provedor": "anthropic", "modelo": "claude-opus-5-5" }
  },
  "alternativos": {
    "leve":  [{ "provedor": "google", "modelo": "<modelo Flash do Gemini>" }],
    "medio": [{ "provedor": "openai", "modelo": "<modelo de código da OpenAI>" }]
  },
  "precos_por_milhao": {
    "claude-haiku-5-5":  { "entrada": null, "saida": null }
  }
}
```

- **leve**: triagem, classificação, resumos, formatação, checagens simples.
- **medio**: análise de código, implementação, revisão por arquivo.
- **forte**: líder do time, planejamento, consolidação, decisões de risco.

Preços ficam em configuração (com `null` até serem preenchidos com a tabela oficial), nunca fixos no código.

## 1.3 Chaves e segurança

- `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY` lidas só do ambiente.
- `orchestrator doctor --api` mostra quais provedores estão configurados, sem exibir as chaves.
- Logs e histórico passam por redação de segredos; o conteúdo das tarefas é opcional no histórico.

## 1.4 Teto de custo

- Estimativa antes de executar (tamanho do contexto × preço do modelo escolhido), exibida no plano.
- Teto por execução (`--teto-usd`, padrão configurável) e teto diário. Ultrapassar interrompe a execução e registra o motivo.

## 1.5 Primeira tarefa ponta a ponta

`orchestrator tarefa "Explique o módulo X" --cwd repo --approve`: um único agente nível médio, com leitura do repositório, resposta em Markdown, custo registrado.

## Critérios de aceite

- Chamada real a pelo menos um provedor com tokens e custo registrados.
- Execução bloqueada quando a estimativa passa do teto.
- Nenhuma chave aparece em log, histórico ou saída (teste automatizado).
- Testes sem rede usando modelo simulado.
