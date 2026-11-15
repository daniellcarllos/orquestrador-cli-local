"""Modo equipe: Team do Agno com líder forte que delega para membros com modelos mais baratos.

Para tarefas abertas, em que a divisão do trabalho não é conhecida de antemão. Os fluxos fixos
(revisar, analisar, desenvolver) são mais baratos e previsíveis; use o time quando eles não servirem.
O teto é conferido antes (estimativa) e o gasto real de líder e membros é registrado por agente.
"""

from __future__ import annotations

import time

from agno.agent import Agent
from agno.team import Team

from . import custos, modelos
from .agentes import PAPEIS, REGRA_DADOS, Contexto
from .registro import Etapa
from .segredos import redigir

MEMBROS = ("analista", "revisor", "planejador")
MAX_ITERACOES = 6


def _registrar(ctx: Contexto, rotulo: str, escolha: modelos.Escolha, metrics, duracao_ms: int) -> None:
    etapa = ctx.execucao.adicionar(Etapa(papel=rotulo, nivel=escolha.nivel, provedor=escolha.provedor,
                                         modelo=escolha.modelo, status="ok", duracao_ms=duracao_ms))
    etapa.tokens_entrada = int(getattr(metrics, "input_tokens", 0) or 0)
    etapa.tokens_saida = int(getattr(metrics, "output_tokens", 0) or 0)
    etapa.custo_usd = custos.custo(etapa.tokens_entrada, etapa.tokens_saida, custos.preco(ctx.catalogo, escolha.modelo))
    ctx.orcamento.registrar(escolha.modelo, etapa.tokens_entrada + etapa.tokens_saida, etapa.custo_usd)


def executar(ctx: Contexto, tarefa: str, modo: str = "coordinate") -> str:
    if modo not in ("coordinate", "route", "broadcast"):
        raise ValueError("Modo de equipe inválido.")
    tarefa = redigir(tarefa)
    simulado = ctx.simulado is not None
    escolhas = {}
    membros = []
    for nome in MEMBROS:
        papel = PAPEIS[nome]
        nivel = ctx.nivel_forcado or ("medio" if papel.nivel == "forte" else papel.nivel)  # membros não usam o forte
        e = modelos.escolher(ctx.catalogo, nivel, simulado=simulado)
        escolhas[nome] = e
        ferramentas = [ctx.repo.listar_arquivos, ctx.repo.ler_arquivo, ctx.repo.buscar_texto] \
            if papel.usa_repositorio and ctx.repo else None
        membros.append(Agent(name=nome, role=papel.instrucoes.split(".")[0],
                             model=modelos.criar_modelo(e, ctx.simulado, papel=nome),
                             instructions=[papel.instrucoes, REGRA_DADOS], tools=ferramentas, markdown=True))
    lider = modelos.escolher(ctx.catalogo, ctx.nivel_forcado or "forte", simulado=simulado)
    ctx.orcamento.verificar(custos.estimar(ctx.catalogo, lider.modelo, tarefa) or None,
                            custos.tokens_estimados(tarefa) * (len(MEMBROS) + 1))

    from agno.team import TeamMode

    time_ = Team(name="equipe", members=membros, mode=getattr(TeamMode, modo),
                 model=modelos.criar_modelo(lider, ctx.simulado, papel="lider"),
                 instructions=["Delegue só o necessário: cada membro recebe apenas a parte que lhe cabe.",
                               "Consolide as respostas dos membros numa resposta final objetiva.", REGRA_DADOS],
                 max_iterations=MAX_ITERACOES, markdown=True)
    inicio = time.monotonic()
    saida = time_.run(tarefa)
    duracao = round((time.monotonic() - inicio) * 1000)

    for resposta in getattr(saida, "member_responses", None) or []:
        nome = getattr(resposta, "agent_name", None) or "membro"
        if nome in escolhas and getattr(resposta, "metrics", None) is not None:
            _registrar(ctx, f"membro:{nome}", escolhas[nome], resposta.metrics, 0)
    # métricas do time incluem o líder; descontar membros quando o Agno os somar
    lider_metrics = saida.metrics
    membros_tokens = sum(e.tokens_entrada + e.tokens_saida for e in ctx.execucao.etapas if e.papel.startswith("membro:"))
    if lider_metrics is not None and (getattr(lider_metrics, "total_tokens", 0) or 0) > membros_tokens > 0:
        class _M:  # só o líder
            input_tokens = max(0, (lider_metrics.input_tokens or 0) - sum(e.tokens_entrada for e in ctx.execucao.etapas if e.papel.startswith("membro:")))
            output_tokens = max(0, (lider_metrics.output_tokens or 0) - sum(e.tokens_saida for e in ctx.execucao.etapas if e.papel.startswith("membro:")))
        lider_metrics = _M
    _registrar(ctx, "lider", lider, lider_metrics, duracao)

    conteudo = saida.content if isinstance(saida.content, str) else str(saida.content or "")
    if not conteudo.strip():
        raise ValueError("A equipe não produziu resposta.")
    return conteudo
