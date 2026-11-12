# Revisão com prompt existente no MCP

A integração MCP é opcional e usa o SDK MCP Python, sem SDK de provedor de modelos. Para habilitá-la, instale a dependência opcional em um ambiente autorizado (`python3 -m pip install '.[mcp]'`), ou use um ambiente Python existente que contenha `mcp` 2.3.x. As outras funcionalidades continuam sem dependências de runtime. A instalação não é executada automaticamente.

Configure `MCP_PROMPTS_URL` com a URL HTTPS do endpoint MCP e `MCP_PROMPTS_TOKEN` no ambiente por um mecanismo seguro. A URL não aceita usuário, senha, token na query ou fragmento; a chave é enviada no cabeçalho de autenticação ao servidor, e não ao subprocesso da CLI. Não armazene credenciais neste repositório ou no histórico do terminal.

Escolha explicitamente um prompt de revisão, um diff ou arquivo UTF-8 autorizado (até 200 KB), grupo e projeto esperados. Substitua os valores de exemplo pelos da sua biblioteca:

```sh
python3 -m orchestrator run "Revisar o diff .NET/C#" \
  --policy examples/policies/policy.claude.example.json \
  --mcp-prompt-id ID_DO_REVISOR \
  --mcp-project "PROJETO" --mcp-group "GRUPO" \
  --input-file /caminho/privado/revisao.diff \
  --approve-mcp --approve
```

`--approve-mcp` autoriza a consulta remota dos IDs escolhidos e `--approve` autoriza executar a CLI e enviar a ela a tarefa, o diff e os documentos recuperados. Para incluir contexto adicional, acrescente `--mcp-context-id ID_DO_CONTEXTO` uma vez por documento; o primeiro ID é a referência de revisão e os demais são dados de contexto potencialmente desatualizados. São aceitos até cinco documentos no total, com limites de tamanho. A revisão é exibida no terminal; não cria comentário em PR nem altera arquivos automaticamente. Confira a resposta antes de compartilhá-la.

Para descobrir metadados atualizados antes de selecionar documentos, liste por projeto e grupo, opcionalmente filtrando uma tag:

```sh
python3 -m orchestrator mcp-list --project "PROJETO" --group "GRUPO" --tag "TAG" --approve-mcp
```

Para selecionar contexto por tag durante uma revisão, adicione `--mcp-context-tag TAG --mcp-max-contexts 2` ao comando `run` acima. O orquestrador consulta a listagem a cada execução (percorrendo todas as páginas, até 10 000 itens), exclui IDs já escolhidos e seleciona até dois documentos (limite configurável de 1 a 4) na ordem retornada pelo servidor, que neste servidor é por atualização mais recente. Ele mostra quantos foram encontrados, os metadados escolhidos e, depois da leitura, os IDs e versões efetivos. Falha se não houver um contexto adicional, se o grupo/projeto divergir ou se a tag tiver mudado. Pode haver alteração entre listagem e leitura; não é um snapshot transacional. A seleção usa apenas correspondência exata de tag, não relevância semântica ou validação da regra de negócio. Use tags específicas por repositório e assunto, revise a seleção e as datas. A aprovação da leitura também autoriza incluir no modelo os documentos selecionados por essa tag; o código não armazena seus textos.

Essas opções não implementam indexação ou RAG e não buscam automaticamente conteúdo em outros projetos. Para reduzir dados e tokens, prefira poucos documentos específicos e um diff revisado para remover conteúdo sensível.

Cada resposta é conferida localmente contra o ID, grupo e projeto fornecidos; divergência interrompe a execução. Esse filtro ocorre **após** o servidor devolver os dados e não é controle de acesso: o servidor MCP precisa aplicar autorização adequada antes da consulta. Confirme que o provedor/modelo, a assinatura e as políticas da organização permitem receber o diff e os documentos. Os textos não são armazenados no histórico do orquestrador, mas são enviados à CLI escolhida e podem ser mantidos ou processados conforme as políticas dela.

