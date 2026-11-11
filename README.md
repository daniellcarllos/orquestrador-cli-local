# Orquestrador CLI local

Protótipo Python local de orquestração **single**, usando CLIs instaladas e autenticadas pelo próprio usuário. Não requer chaves de API nem dependências de runtime; não inclui serviço web ou modo team. Usa a biblioteca padrão do Python 3.10+.

```sh
python3 -m orchestrator doctor
python3 -m orchestrator plan "Revisar este código" --cwd .
python3 -m orchestrator run "Revisar este código" --agent codex --cwd . --mode single --approve
python3 -m orchestrator history
python3 -m unittest discover -s tests -v
```

`run` exige `--approve`, que autoriza a execução e consumo de cota da CLI selecionada. Sem isso, somente apresenta o plano. A ordem padrão é Codex, Claude, Gemini; `--agent` substitui a escolha. Detectar uma CLI no PATH não comprova que esteja autenticada ou que a versão aceite as flags. Consulte os termos, limites e políticas de dados antes de usar.

## Limites de segurança

O protótipo é para **análise**: Codex é invocado em sandbox `read-only`; Claude em modo restrito com ferramentas internas desativadas; Gemini em modo `plan`. Os modos e seus efeitos dependem da versão e configuração locais. Eles **não garantem isolamento completo**, bloqueio de rede, de plugins/hooks, acesso a segredos ou ausência de efeitos; valide-os no ambiente antes de confiar dados. Nenhuma CLI real foi invocada nos testes. Não use para tarefas que precisem de alterações. A aplicação não é uma barreira de segurança de sistema operacional.

O roteamento verifica disponibilidade no PATH, não políticas de dados ou capacidades reais; se o agente não for autorizado a receber a tarefa, não a execute. Não há fallback automático nem retries. A saída de processo zero não comprova sucesso funcional. Saídas têm tamanho limitado e redação básica, não exaustiva: revise antes de compartilhar. O prompt passa por stdin e não é armazenado pelo orquestrador, mas as próprias CLIs podem reter dados segundo suas configurações e políticas.

O histórico local contém apenas identificador, agente, versão de política, duração e status, em `~/.local/state/orquestrador-cli-local/history.jsonl`. Defina `ORCHESTRATOR_STATE_DIR` para outro local seguro. Arquivos novos usam modo 600 e diretórios novos modo 700; permissões preexistentes devem ser revisadas pelo usuário. O registro não é uma trilha de auditoria imutável.

## Evolução

Verificar autenticação e capacidades por versão; definir política de dados por projeto; desenhar autorização de escrita e integração de diff/testes em ambiente isolado; integrar contexto MCP/RAG somente com isolamento e consentimento; implementar team apenas depois do aceite de single. A V1 não automatiza deploy, push ou tarefas remotas.
