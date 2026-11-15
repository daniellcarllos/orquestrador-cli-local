# Painel web

Interface para usar o orquestrador sem decorar comandos: escolher tarefa, repositório e configurações, executar, acompanhar cada agente ao vivo, ler o resultado e agir sobre ele. Inclui o escritório em 16 bits, com um posto por papel da equipe.

## Como rodar

```sh
cd web && npm install && npm run build && cd ..
.venv/bin/python -m orchestrator serve       # --port para trocar a porta
```

O `serve` imprime um endereço como `http://127.0.0.1:8765/#token=...`. Abra exatamente esse endereço: o token muda a cada inicialização e fica só naquela aba do navegador. Para os fluxos por API, rode o `serve` com o Python do ambiente que tem o extra `[api]`.

## Abas

- **Nova tarefa:** fluxo, repositório (com favoritos e verificação de branch e alterações pendentes), campos de cada fluxo, configurações da execução (simulado, tetos, nível dos modelos) e ações ao terminar. **Ver plano** roda `--so-plano` e mostra papéis e modelos sem custo. **Executar** abre um resumo para confirmar.
- **Execuções:** lista desta sessão e do histórico. Mostra as etapas ao vivo, com personagem, modelo, tokens, custo e status, além do log, do resultado em Markdown, dos patches propostos (aplicar exige confirmação) e das ações sobre o resultado, com prévia do texto antes de enviar.
- **Escritório:** a visão em pixel art descrita abaixo.
- **Configurações:** provedores com chave (só sim ou não), modelo de cada nível e preços, salvos em `~/.local/state/orquestrador-cli-local/modelos.json`; padrões de teto e repositórios favoritos.
- **Como usar:** passo a passo e qual fluxo escolher.

Atalho: `?aba=execucoes` (ou `nova`, `escritorio`, `configuracoes`, `ajuda`) abre direto numa aba.

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

## API local

Todas as rotas exigem o cabeçalho `X-Painel-Token`. Rotas de escrita exigem corpo JSON e `Origin` do próprio painel.

| Rota | Conteúdo |
|---|---|
| `GET /api/history` | Últimas 500 entradas do histórico |
| `GET /api/doctor?probe=1` | Inventário das CLIs |
| `GET, PUT, DELETE /api/catalogo` | Catálogo de modelos em uso; salvar ou restaurar o padrão |
| `GET /api/ambiente` | Se o extra de API está instalado, políticas e ações disponíveis |
| `GET /api/repositorio?caminho=` | Informações git do repositório (branch, branches, alterações) |
| `GET, PUT /api/repositorios` | Repositórios favoritos |
| `POST /api/plano` | Plano de uma execução, sem custo |
| `POST /api/execucoes` | Inicia uma execução em segundo plano (máximo de 2 simultâneas) |
| `GET /api/execucoes[/id]` | Estado, log e saída das execuções desta sessão |
| `POST /api/execucoes/id/cancelar` | Cancela |
| `GET /api/resultados/id` | Metadados, resultado e patches de uma execução |
| `POST /api/resultados/id/acao` | Executa uma ação sobre o resultado (exige `confirmado`) |
| `POST /api/resultados/id/aplicar` | Aplica um patch com o SHA-256 conferido (exige `confirmado`) |

## Segurança

- Escuta só em localhost e confere o cabeçalho `Host`, o que bloqueia DNS rebinding.
- Token de sessão aleatório a cada `serve`, comparado em tempo constante. Ele viaja no fragmento da URL, que não é enviado ao servidor nem gravado em logs.
- Escrita só com `Content-Type: application/json` e `Origin` do painel, o que impede formulários e páginas de outros sites.
- Execuções rodam o próprio CLI em subprocesso, sem shell. Só fluxos e opções conhecidos são aceitos, valores vão como `--opcao=valor` e textos livres depois de `--`, para que nada digitado vire opção.
- Aplicar patch e ações externas exigem confirmação explícita na interface. Chaves de API nunca passam pelo painel.
