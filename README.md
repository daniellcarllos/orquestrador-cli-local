# Orquestrador CLI local

Protótipo Python local de orquestração **single**, usando CLIs instaladas e autenticadas pelo próprio usuário. Não requer chaves de API nem dependências de runtime; não inclui serviço web ou modo team. Usa a biblioteca padrão do Python 3.10+.

```sh
python3 -m orchestrator doctor
python3 -m orchestrator plan "Revisar este código" --cwd .
python3 -m orchestrator run "Revisar este código" --agent codex --cwd . --mode single --approve
python3 -m orchestrator prepare "Propor alteração" --cwd /caminho/projeto --output /caminho/proposta --approve
# Revise /caminho/proposta/changes.patch e copie o hash exibido ao preparar:
python3 -m orchestrator apply /caminho/proposta --cwd /caminho/projeto --approve-sha256 HASH_REVISADO
python3 -m orchestrator history
python3 -m unittest discover -s tests -v
```

`run` exige `--approve`, que autoriza a execução e consumo de cota da CLI selecionada. Sem isso, somente apresenta o plano. A ordem padrão é Codex, Claude, Gemini; `--agent` substitui a escolha. Detectar uma CLI no PATH não comprova que esteja autenticada ou que a versão aceite as flags. Consulte os termos, limites e políticas de dados antes de usar.

## Limites de segurança

`run` é para **análise**: Codex é invocado em sandbox `read-only`; Claude em modo restrito com ferramentas internas desativadas; Gemini em modo `plan`. `prepare` utiliza somente Codex, com `workspace-write`, em uma cópia temporária de arquivos rastreados de um repositório limpo. A proposta deve ficar fora da origem. Arquivos `.env`, diretórios de credenciais comuns, dependências e links simbólicos são excluídos ou rejeitados, mas a filtragem não detecta todos os segredos. Não inclua conteúdo restrito no repositório enviado à CLI.

Revise o patch inteiro, inclusive alterações destrutivas e conteúdo sensível, antes de passar seu SHA-256 a `apply`. A aplicação exige mesma revisão base, árvore limpa e hash exato. O hash detecta mudança após a revisão, mas não atesta segurança. Depois confira o diff e rode testes; o orquestrador não os executa automaticamente. Arquivos de proposta podem conter informações sensíveis: mantenha-os em local privado e remova-os conforme sua política de retenção.

Os modos e seus efeitos dependem da versão e configuração locais. A cópia e as flags **não garantem isolamento completo**, bloqueio de rede ou comandos remotos, nem impedem acesso a plugins, hooks, credenciais ou dados externos; valide as proteções do ambiente antes de executar. O orquestrador não é uma barreira de segurança de sistema operacional. Nenhuma CLI real foi invocada nos testes. A aplicação não faz push, deploy ou conexão remota por conta própria, mas não consegue garantir que um agente configurado não tente fazê-lo.

O roteamento verifica disponibilidade no PATH, não políticas de dados ou capacidades reais; se o agente não for autorizado a receber a tarefa, não a execute. Não há fallback automático nem retries. A saída de processo zero não comprova sucesso funcional. Saídas têm tamanho limitado e redação básica, não exaustiva: revise antes de compartilhar. O prompt passa por stdin e não é armazenado pelo orquestrador, mas as próprias CLIs podem reter dados segundo suas configurações e políticas.

O histórico local contém apenas identificador, agente, versão de política, duração e status, em `~/.local/state/orquestrador-cli-local/history.jsonl`. Defina `ORCHESTRATOR_STATE_DIR` para outro local seguro. Arquivos novos usam modo 600 e diretórios novos modo 700; permissões preexistentes devem ser revisadas pelo usuário. O registro não é uma trilha de auditoria imutável.

## Evolução

Verificar autenticação e capacidades por versão; definir política de dados por projeto; fortalecer o isolamento e integrar execução e validação de testes; integrar contexto MCP/RAG somente com isolamento e consentimento; implementar team apenas depois do aceite de single.
