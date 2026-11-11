# Orquestrador CLI local

Protótipo Python local de orquestração **single**, usando CLIs instaladas e autenticadas pelo próprio usuário. Não requer chaves de API nem dependências de runtime; não inclui serviço web ou modo team. Usa a biblioteca padrão do Python 3.10+.

```sh
python3 -m orchestrator doctor
python3 -m orchestrator doctor --probe
python3 -m orchestrator plan "Revisar este código" --cwd .
python3 -m orchestrator plan "Revisar este código" --policy policy.example.json --cwd .
python3 -m orchestrator plan "Planejar uma funcionalidade" --policy policy.claude.example.json --cwd .
python3 -m orchestrator run "Revisar este código" --agent codex --cwd . --mode single --approve
python3 -m orchestrator prepare "Propor alteração" --cwd /caminho/projeto --output /caminho/proposta --approve
python3 -m orchestrator prepare "Propor alteração" --agent claude --cwd /caminho/projeto --output /caminho/proposta-claude --approve
# Revise /caminho/proposta/changes.patch e copie o hash exibido ao preparar:
python3 -m orchestrator apply /caminho/proposta --cwd /caminho/projeto --approve-sha256 HASH_REVISADO
python3 -m orchestrator history
python3 -m unittest discover -s tests -v
```

`run` exige `--approve`, que autoriza a execução e consumo de cota da CLI selecionada. Sem isso, somente apresenta o plano. A ordem padrão é Codex, Claude, Gemini; `--agent` substitui a escolha. Detectar uma CLI no PATH não comprova que esteja autenticada ou que a versão aceite as flags. Consulte os termos, limites e políticas de dados antes de usar.

## Inventário e roteamento

`doctor --probe` executa localmente os comandos de versão e ajuda das CLIs instaladas. Ele indica opções observadas, inclusive seleção de modelo, JSON, sandbox e sessão. Ajuda não comprova que um modelo exista, esteja disponível na conta, aceite determinada tarefa, ou que a autenticação e o plano de uso sejam válidos. Sem `--probe`, só verifica o PATH. Nenhum dos modos verifica tokens ou consulta a sessão de autenticação.

`--policy arquivo.json` ativa uma política explícita para `plan`, `run` ou `prepare`. Veja `policy.example.json`: é um exemplo de estrutura, não uma recomendação de custo, segurança ou escolha de modelo. Configure em cada nível (`simples`, `média`, `alta`) uma lista ordenada de agentes autorizados e seus identificadores de modelo; `null` usa o padrão da CLI. Escolha apenas modelos conhecidos, disponíveis, autorizados para seus dados e permitidos pela sua assinatura. O orquestrador não descobre nem valida a lista de modelos da conta. Se indicar um modelo, a execução confirma antes que a ajuda da CLI anuncia `--model`; falha se não puder confirmar, mas isso não garante que o identificador seja aceito.

O classificador usa regras simples e auditáveis por palavras e tamanho; não mede inteligência ou qualidade e pode errar. O roteador usa o primeiro candidato disponível no PATH no nível classificado; não verifica autenticação nem troca automaticamente após uma execução falhar. Uma escolha `--agent` deve constar no nível autorizado, caso contrário falha. Se nenhum candidato estiver disponível, falha de forma segura. Em `prepare`, Gemini não é elegível para escrita: inclua Codex ou Claude no nível correspondente. Sem política, mantém a ordem de compatibilidade anterior e não afirma otimização. `plan` apenas descreve a seleção; `run` e `prepare` continuam exigindo aprovação da execução.

Para experimentar o direcionamento dentro do Claude Code, `policy.claude.example.json` associa tarefas simples a `haiku`, implementação intermediária a `sonnet`, e planejamento ou conferência a `opus`. Por exemplo, `formatar um texto` seleciona Haiku; `implementar código`, Sonnet; `planejar arquitetura` ou `revisar código`, Opus. Cada solicitação continua sendo uma única chamada: esses papéis não criam uma cadeia de vários agentes. Os aliases são exemplos sujeitos à disponibilidade da CLI, da conta e às condições de uso; a política é opcional e não é ativada automaticamente. Revise-a antes de usar e compare os resultados com uma referência de modelo único.

Tokens, custo, economia e qualidade permanecem **desconhecidos**. O roteador não reduz automaticamente o contexto nem prova que um modelo seja o melhor; confirme a escolha com avaliações e medições reais antes de tomar decisões baseadas em economia.

## Limites de segurança

`run` é para **análise**: Codex é invocado em sandbox `read-only`; Claude em modo restrito com ferramentas internas desativadas; Gemini em modo `plan`. `prepare` aceita Codex (padrão, com `workspace-write`) ou `--agent claude` em uma cópia temporária de arquivos rastreados de um repositório limpo. Para Claude, usa as flags observadas na versão 2.1.322: `--restricted`, `--strict-mcp-config`, ferramentas de arquivo, `--permission-mode acceptEdits`, `--permission-prompts none` e `--no-session-persistence`. Outras versões ou políticas gerenciadas podem se comportar de forma diferente. A proposta deve ficar fora da origem. Arquivos `.env`, diretórios de credenciais comuns, dependências e links simbólicos são excluídos ou rejeitados, mas a filtragem não detecta todos os segredos. Não inclua conteúdo restrito no repositório enviado à CLI.

Para usar Claude, instale e autentique o Claude Code pelos meios oficiais e verifique `claude --version` e `claude auth status`. O orquestrador usa a sessão da própria CLI e não pede que se copie token ou chave. Consulte os [termos da Anthropic para autenticação e uso de Claude Code](https://code.claude.com/docs/en/legal-and-compliance): eles diferenciam uso pessoal do CLI e aplicações de terceiros que encaminham requisições via credenciais de assinatura. Confirme a elegibilidade do seu uso antes de automatizá-lo; a existência de uma sessão não comprova essa elegibilidade.

Revise o patch inteiro, inclusive alterações destrutivas e conteúdo sensível, antes de passar seu SHA-256 a `apply`. A aplicação exige mesma revisão base, árvore limpa e hash exato. O hash detecta mudança após a revisão, mas não atesta segurança. Depois confira o diff e rode testes; o orquestrador não os executa automaticamente. Arquivos de proposta podem conter informações sensíveis: mantenha-os em local privado e remova-os conforme sua política de retenção.

Os modos e seus efeitos dependem da versão e configuração locais. A cópia e as flags **não garantem isolamento completo**, bloqueio de rede ou comandos remotos, nem impedem acesso a plugins, hooks, credenciais ou dados externos; valide as proteções do ambiente antes de executar. O orquestrador não é uma barreira de segurança de sistema operacional. Nenhuma CLI real foi invocada nos testes. A aplicação não faz push, deploy ou conexão remota por conta própria, mas não consegue garantir que um agente configurado não tente fazê-lo.

O roteamento verifica disponibilidade no PATH e a política de candidatos fornecida, mas não comprova conformidade com políticas de dados ou capacidades reais; se o agente não for autorizado a receber a tarefa, não a execute. Não há nova execução automática nem retries. A saída de processo zero não comprova sucesso funcional. Saídas têm tamanho limitado e redação básica, não exaustiva: revise antes de compartilhar. O prompt passa por stdin e não é armazenado pelo orquestrador, mas as próprias CLIs podem reter dados segundo suas configurações e políticas.

O histórico local contém apenas identificador, agente, versão de política, duração e status, em `~/.local/state/orquestrador-cli-local/history.jsonl`. Defina `ORCHESTRATOR_STATE_DIR` para outro local seguro. Arquivos novos usam modo 600 e diretórios novos modo 700; permissões preexistentes devem ser revisadas pelo usuário. O registro não é uma trilha de auditoria imutável.

## Evolução

Verificar autenticação e disponibilidade de modelos por CLI; definir política de dados por projeto; medir uso e avaliar qualidade; fortalecer o isolamento e integrar execução e validação de testes; integrar contexto MCP/RAG somente com isolamento e consentimento; implementar team apenas depois do aceite de single.
