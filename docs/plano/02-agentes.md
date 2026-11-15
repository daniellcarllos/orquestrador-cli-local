# Etapa 2: agentes especialistas e ferramentas

Meta: um conjunto pequeno de agentes, cada um com papel, modelo, ferramentas e formato de resposta próprios. Cada agente roda sozinho (modo single) antes de entrar em time.

## 2.1 Agentes

| Agente | Nível de modelo | Ferramentas | Saída estruturada |
|---|---|---|---|
| Triagem | leve | nenhuma | tipo de tarefa, complexidade, arquivos envolvidos, custo estimado |
| Analista de código | médio | ler arquivos, buscar no repo | módulos, responsabilidades, dependências, riscos |
| Revisor de PR | médio (forte em diff grande ou de segurança) | ler diff, ler arquivos, biblioteca MCP | achados com arquivo, linha, severidade, correção sugerida, veredito |
| Implementador | médio | ler arquivos, propor patch (sem escrever na origem) | patch + resumo |
| Testador | leve ou médio | rodar comando de teste permitido | comandos executados, resultado, falhas |
| Coordenador | forte | delegar para membros | plano, consolidação, decisão |

As instruções de cada papel podem vir da biblioteca MCP. O Revisor de PR usa o prompt "Code reviewer .NET/C# para PRs do Azure DevOps" (ID `93d6961d2a`) como base.

## 2.2 Ferramentas limitadas

Ferramentas próprias, em vez das genéricas de shell do Agno:

- **ler_arquivo / listar / buscar**: só dentro do repositório informado, com limite de tamanho, ignorando `.env`, `.git`, credenciais e binários.
- **git_diff**: diff entre dois commits ou da branch contra a base, já filtrado de segredos.
- **rodar_testes**: só comandos de uma lista branca do projeto (por exemplo `dotnet test`, `pytest`), em cópia temporária, com timeout.
- **propor_patch**: grava o patch na pasta da execução, reaproveitando `changes.py`. Aplicar continua sendo `apply` com hash revisado.
- **biblioteca_mcp**: leitura de prompts e contextos via `MCPTools` do Agno ou do cliente atual, com chave de leitura restrita.

Nenhum agente recebe shell livre.

## 2.3 Saídas estruturadas

Cada agente declara um esquema (Pydantic) e o Agno valida a resposta. Exemplo do Revisor:

```python
class Achado(BaseModel):
    arquivo: str
    linha: int | None
    severidade: Literal["critico", "alto", "medio", "baixo", "info"]
    categoria: Literal["seguranca", "bug", "desempenho", "estilo", "teste"]
    descricao: str
    correcao: str | None

class Revisao(BaseModel):
    resumo: str
    achados: list[Achado]
    veredito: Literal["aprovar", "aprovar_com_ressalvas", "ajustar"]
```

Resposta inválida tem uma nova tentativa com o erro de validação; se falhar de novo, a etapa termina com status `fora_do_contrato`.

## 2.4 Comandos

```sh
orchestrator analisar --cwd repo "Como funciona a autenticação?"
orchestrator revisar --cwd repo --base main --head feature/x
orchestrator revisar --diff pr.diff --mcp-prompt-id 93d6961d2a
```

## Critérios de aceite

- Revisão de um diff real gera `revisao.json` válido e `revisao.md` legível.
- Ferramentas recusam caminho fora do repositório e arquivos sensíveis (testes).
- Cada agente registra modelo, tokens e custo por execução.
