# Etapa 4: ações ao finalizar e aprovação

Meta: quando uma tarefa termina, o orquestrador executa uma ação definida, como comentar na PR, salvar na biblioteca ou notificar, sempre respeitando o nível de aprovação de cada ação.

## 4.1 Onde a ação acontece

- **Última etapa do workflow**: recebe o resultado validado e chama a ação. É o caminho principal, porque fica visível no plano e no histórico.
- **Hook pós-execução**: para ações transversais, como registrar métricas ou notificar, que valem para qualquer fluxo.

## 4.2 Catálogo de ações

| Ação | Efeito | Aprovação |
|---|---|---|
| `salvar_arquivo` | Grava `resultado.md` / `.json` na pasta da execução | Automática |
| `salvar_na_biblioteca` | Cria ou atualiza item na biblioteca MCP (tipo documentação) | Automática se a chave for de escrita restrita ao grupo; senão pede |
| `notificar` | Mensagem curta (macOS, e-mail ou webhook configurado) sem conteúdo sensível | Automática |
| `comentar_pr_azure` | Publica a revisão como comentários na PR do Azure DevOps | Explícita, mostrando o texto final |
| `comentar_pr_github` | Idem no GitHub | Explícita |
| `abrir_pr` | Cria branch e PR com o patch aprovado | Explícita, após `apply` revisado |
| `encadear` | Inicia outro fluxo com o resultado (por exemplo, revisão após implementação) | Herda a aprovação do fluxo seguinte |

## 4.3 Regras

- Ações com efeito externo nunca disparam em segundo plano sem aprovação. No modo não interativo, só rodam se a execução foi iniciada com `--aprovar-acoes comentar_pr_azure` (lista explícita).
- O conteúdo publicado é exatamente o que foi aprovado: hash do texto conferido no momento do envio.
- Credenciais de Azure DevOps e GitHub vêm do ambiente (`AZURE_DEVOPS_PAT`, `GITHUB_TOKEN`) e têm o menor escopo possível.
- Falha na ação não apaga o resultado: ele continua salvo e a ação pode ser repetida com `orchestrator acao <id> <nome>`.

## 4.4 Configuração por fluxo

```json
{
  "fluxo": "code_review",
  "ao_finalizar": [
    { "acao": "salvar_arquivo" },
    { "acao": "notificar", "quando": "sempre" },
    { "acao": "comentar_pr_azure", "quando": "veredito != 'aprovar'", "aprovacao": "explicita" }
  ]
}
```

## Critérios de aceite

- Code review termina, salva o resultado e, após aprovação, publica comentários numa PR de teste do Azure DevOps.
- Sem aprovação, nenhuma ação externa acontece (teste automatizado).
- Ação repetível a partir do histórico.
