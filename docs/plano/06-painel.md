# Etapa 6: painel com postos, filas e respostas

Meta: o escritório em 16 bits passa a refletir a equipe real. Cada posto é um agente especialista, com o modelo que está usando, o que está fazendo agora, o que entregou e quanto custou.

## 6.1 Personagens originais

Os sprites atuais são inspirados em personagens da Marvel, que pertencem a terceiros. Eles serão substituídos por personagens **originais**, criados para o projeto, um por agente:

| Posto | Personagem original | Visual |
|---|---|---|
| Portaria (aprovações) | Guarda | Uniforme azul, quepe, prancheta |
| Coordenador | Coordenadora | Terno cinza, fone de ouvido, mapa na parede |
| Triagem | Recepcionista | Camisa amarela, carimbo, bandeja de entrada |
| Analista de código | Cartógrafa | Colete verde-água, lupa, mapa de módulos |
| Revisor de PR | Inspetora | Óculos, colete verde, prancheta com checklist |
| Implementador | Engenheiro | Macacão laranja, capacete, chave inglesa |
| Testador | Técnica de laboratório | Jaleco branco, tubos de ensaio coloridos |
| Arquivo (histórico e custos) | Arquivista | Avental marrom, caixas, calculadora |

Cada sala mostra também o **modelo** em uso naquele momento (leve, médio ou forte, com o ID) e o provedor.

## 6.2 O que cada sala mostra

- Estado: TRABALHANDO, AGUARDANDO APROVAÇÃO, OCIOSO, FORA DO AR (sem chave do provedor).
- Fila: etapas pendentes daquele posto.
- Última entrega: trecho da resposta, status e duração, com link para a resposta completa.
- Placar: execuções, taxa de sucesso, tempo médio, **tokens e custo** do dia.

## 6.3 Visão de execução

Ao clicar numa execução, uma linha do tempo mostra as etapas do fluxo com o personagem de cada agente, o modelo usado, tokens, custo e status. No paralelo, as respostas aparecem lado a lado. As ações ao finalizar aparecem no fim da linha, com indicação de aprovada, pendente ou recusada.

## 6.4 Continua só leitura

O painel não aprova nem dispara execuções nem ações. Aprovação continua no terminal. Aprovação pelo painel, se vier, será proposta separada, com token local e confirmação por ação.

## Critérios de aceite

- Nenhum personagem de terceiros nos sprites, nomes ou textos do painel.
- Linha do tempo de um code review com três revisores em paralelo, custo por agente visível.
- Captura de tela conferida em desktop e celular.
