"""Fluxos de trabalho montados com o Workflow do Agno.

Cada etapa é uma função que chama `Contexto.rodar` (o único ponto que fala com modelos). As etapas
trocam dados estruturados por `ctx.estado`, não textos longos. Qualquer falha (teto, formato, erro do
provedor) para o workflow de forma explícita: não há nova tentativa paga sem controle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agno.workflow import Parallel, Step, StepInput, StepOutput, Workflow
from pydantic import BaseModel

from .. import changes
from . import esquemas
from .agentes import Contexto, dados
from .custos import TetoExcedido
from .ferramentas import AcessoNegado, dividir_diff, rodar_testes

FOCOS_REVISAO = {
    "seguranca": "segurança: injeção, autenticação e autorização, segredos, validação de entrada, dados sensíveis em log",
    "bugs": "correção: lógica, nulos, concorrência, tratamento de erros, recursos não liberados, regressões",
    "qualidade": "manutenção, desempenho e testes: complexidade, duplicação, consultas ineficientes, testes ausentes",
}
MAX_RODADAS = 2
MAX_DIFF_POR_REVISOR = 120_000


class FluxoInterrompido(RuntimeError):
    pass


@dataclass
class Resultado:
    status: str  # ok | interrompido
    saida: BaseModel | str | None
    motivo: str | None = None


def _etapa(nome: str, fn: Callable[[Contexto, StepInput], str], ctx: Contexto) -> Step:
    """Envolve uma função de etapa: erros viram parada explícita do workflow, nunca nova tentativa."""

    def executor(step_input: StepInput) -> StepOutput:
        try:
            return StepOutput(step_name=nome, content=fn(ctx, step_input) or "ok")
        except (TetoExcedido, ValueError, RuntimeError, AcessoNegado) as exc:
            ctx.estado.setdefault("erros", []).append(f"{nome}: {exc}")
            return StepOutput(step_name=nome, content=str(exc), success=False, error=str(exc), stop=True)

    return Step(name=nome, executor=executor, max_retries=0)


def _executar(nome: str, passos: list, ctx: Contexto, entrada: str) -> None:
    Workflow(name=nome, steps=passos).run(input=entrada)
    if ctx.estado.get("erros"):
        raise FluxoInterrompido("; ".join(ctx.estado["erros"]))


# ============================== code review ==============================

def revisar(ctx: Contexto, diff: str, tarefa: str = "Revisar as alterações") -> Resultado:
    if not diff.strip():
        raise ValueError("Diff vazio: nada para revisar.")
    ctx.estado["diff"] = diff

    def triagem(c: Contexto, _: StepInput) -> str:
        arquivos = list(dividir_diff(diff))
        t = c.rodar("triagem", f"{tarefa}\nArquivos alterados: {', '.join(arquivos[:80])}\n"
                               f"Tamanho do diff: {len(diff)} caracteres.")
        c.estado["triagem"] = t
        return t.model_dump_json()

    def revisor(foco: str):
        def fn(c: Contexto, _: StepInput) -> str:
            t: esquemas.Triagem = c.estado["triagem"]
            # escala para o modelo forte só onde vale: segurança em mudança de risco alto
            nivel = "forte" if foco == "seguranca" and t.risco == "alto" else None
            trecho = diff[:MAX_DIFF_POR_REVISOR]
            r = c.rodar("revisor", f"Foco desta revisão: {FOCOS_REVISAO[foco]}\n{dados('Diff', trecho)}",
                        nivel=nivel, rotulo=f"revisor:{foco}")
            c.estado.setdefault("parciais", {})[foco] = r
            return f"{len(r.achados)} achados"
        return fn

    def consolidar(c: Contexto, _: StepInput) -> str:
        parciais = {k: v.model_dump() for k, v in c.estado.get("parciais", {}).items()}
        r = c.rodar("coordenador", "Consolide as revisões parciais numa revisão final com veredito.\n"
                                   + dados("Revisões parciais", parciais), esquema=esquemas.Revisao,
                    rotulo="coordenador:revisao")
        c.estado["final"] = r
        return r.veredito

    _executar("code_review", [
        _etapa("triagem", triagem, ctx),
        Parallel(*[_etapa(f"revisor:{f}", revisor(f), ctx) for f in FOCOS_REVISAO], name="revisores"),
        _etapa("consolidacao", consolidar, ctx),
    ], ctx, tarefa)
    return Resultado("ok", ctx.estado["final"])


def revisao_markdown(r: esquemas.Revisao) -> str:
    ordem = ["critico", "alto", "medio", "baixo", "info"]
    linhas = [f"# Revisão de código\n\n**Veredito:** {r.veredito.replace('_', ' ')}\n\n{r.resumo}\n"]
    for sev in ordem:
        grupo = [a for a in r.achados if a.severidade == sev]
        if not grupo:
            continue
        linhas.append(f"\n## {sev.capitalize()} ({len(grupo)})\n")
        for a in grupo:
            local = f"{a.arquivo}:{a.linha}" if a.linha else a.arquivo
            linhas.append(f"- **{local}** [{a.categoria}] {a.descricao}")
            if a.correcao:
                linhas.append(f"  - Correção sugerida: {a.correcao}")
    if r.limites:
        linhas.append(f"\n## Limites da revisão\n\n{r.limites}")
    return "\n".join(linhas) + "\n"


# ============================== análise ==============================

def analisar(ctx: Contexto, pergunta: str, max_areas: int = 4) -> Resultado:
    if ctx.repo is None:
        raise ValueError("A análise precisa de um repositório (--cwd).")

    def triagem(c: Contexto, _: StepInput) -> str:
        estrutura = c.repo.listar_arquivos(".")
        t = c.rodar("triagem", f"{pergunta}\nListe em 'areas' as pastas mais relevantes (no máximo {max_areas}).\n"
                               + dados("Arquivos do repositório", estrutura[:20_000]))
        c.estado["areas"] = [a for a in t.areas if a.strip()][:max_areas] or ["."]
        return ", ".join(c.estado["areas"])

    _executar("analise:triagem", [_etapa("triagem", triagem, ctx)], ctx, pergunta)

    def analista(area: str):
        def fn(c: Contexto, _: StepInput) -> str:
            r = c.rodar("analista", f"Pergunta: {pergunta}\nÁrea a analisar: {area}", rotulo=f"analista:{area}")
            c.estado.setdefault("modulos", []).append(r)
            return r.area
        return fn

    def consolidar(c: Contexto, _: StepInput) -> str:
        modulos = [m.model_dump() for m in c.estado.get("modulos", [])]
        r = c.rodar("coordenador", f"Responda à pergunta com base nas análises por área.\nPergunta: {pergunta}\n"
                                   + dados("Análises", modulos), esquema=esquemas.Analise, rotulo="coordenador:analise")
        c.estado["final"] = r
        return "ok"

    areas = ctx.estado["areas"]
    paralelo = Parallel(*[_etapa(f"analista:{a}", analista(a), ctx) for a in areas], name="analistas") if len(areas) > 1 \
        else _etapa(f"analista:{areas[0]}", analista(areas[0]), ctx)
    _executar("analise", [paralelo, _etapa("consolidacao", consolidar, ctx)], ctx, pergunta)
    return Resultado("ok", ctx.estado["final"])


def analise_markdown(r: esquemas.Analise) -> str:
    partes = [f"# Análise de código\n\n{r.visao_geral}\n"]
    for m in r.modulos:
        partes.append(f"\n## {m.area}\n\n{m.responsabilidade}\n")
        if m.dependencias:
            partes.append("Dependências: " + ", ".join(m.dependencias) + "\n")
        partes += [f"- Risco: {x}" for x in m.riscos]
    if r.riscos:
        partes.append("\n## Riscos\n\n" + "\n".join(f"- {x}" for x in r.riscos))
    if r.recomendacoes:
        partes.append("\n## Recomendações\n\n" + "\n".join(f"- {x}" for x in r.recomendacoes))
    return "\n".join(partes) + "\n"


# ============================== desenvolvimento em paralelo ==============================

def _validar_plano(plano: esquemas.PlanoDesenvolvimento) -> None:
    vistos: dict[str, str] = {}
    ids = set()
    for s in plano.subtarefas:
        if s.id in ids:
            raise ValueError(f"Subtarefa repetida: {s.id}")
        ids.add(s.id)
        if not s.arquivos:
            raise ValueError(f"Subtarefa {s.id} não declarou arquivos permitidos.")
        for a in s.arquivos:
            if not changes.allowed(Path(a)):
                raise ValueError(f"Subtarefa {s.id} quer alterar caminho não permitido: {a}")
            if a in vistos:
                raise ValueError(f"Subtarefas {vistos[a]} e {s.id} alteram o mesmo arquivo ({a}); não dá para paralelizar.")
            vistos[a] = s.id


def _aplicar_em_copia(origem: Path, base: str, sub: esquemas.Subtarefa, impl: esquemas.Implementacao,
                      destino: Path, comando_teste: str | None) -> dict:
    permitidos = set(sub.arquivos)
    with changes.temporary_copy() as tmp:
        copia = Path(tmp)
        changes.copy_tracked(origem, copia)
        changes.init_copy(copia)
        for arq in impl.arquivos:
            if arq.caminho not in permitidos or not changes.allowed(Path(arq.caminho)):
                raise AcessoNegado(f"Implementação de {sub.id} alterou arquivo fora do permitido: {arq.caminho}")
            alvo = (copia / arq.caminho).resolve()
            if not alvo.is_relative_to(copia.resolve()):
                raise AcessoNegado("Caminho fora da cópia.")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(arq.conteudo, encoding="utf-8")
        # O patch é exportado antes dos testes: artefatos gerados por eles (caches, relatórios) não entram.
        meta = changes.export_patch(copia, destino, base)
        meta["patch"] = (destino / "changes.patch").read_text(encoding="utf-8", errors="replace")
        teste = rodar_testes(copia, comando_teste, [comando_teste]) if comando_teste else None
    meta["teste"] = teste
    return meta


def desenvolver(ctx: Contexto, objetivo: str, comando_teste: str | None = None, max_subtarefas: int = 4) -> Resultado:
    if ctx.repo is None:
        raise ValueError("O desenvolvimento precisa de um repositório (--cwd).")
    origem = ctx.repo.raiz
    base = changes.validate_source(origem)  # repositório Git limpo, na raiz

    def planejar(c: Contexto, _: StepInput) -> str:
        p = c.rodar("planejador", f"Objetivo: {objetivo}\nNo máximo {max_subtarefas} subtarefas.\n"
                                  + dados("Arquivos do repositório", c.repo.listar_arquivos(".")[:20_000]))
        p.subtarefas = p.subtarefas[:max_subtarefas]
        _validar_plano(p)
        c.estado["plano"] = p
        return f"{len(p.subtarefas)} subtarefas"

    _executar("desenvolvimento:plano", [_etapa("planejamento", planejar, ctx)], ctx, objetivo)
    plano: esquemas.PlanoDesenvolvimento = ctx.estado["plano"]

    def frente(sub: esquemas.Subtarefa):
        def fn(c: Contexto, _: StepInput) -> str:
            ajustes = None
            for rodada in range(1, MAX_RODADAS + 1):
                pedido = dados("Subtarefa", sub)
                if ajustes:
                    pedido += "\n" + dados("Ajustes pedidos pela revisão anterior", ajustes)
                impl = c.rodar("implementador", pedido, rotulo=f"implementador:{sub.id}", rodada=rodada)
                destino = c.execucao.pasta / f"proposta-{sub.id}-r{rodada}"
                meta = _aplicar_em_copia(origem, base, sub, impl, destino, comando_teste)
                rev = c.rodar("revisor", f"Revise o patch da subtarefa contra os critérios de aceite.\n"
                                         + dados("Subtarefa", sub) + "\n" + dados("Patch", meta["patch"][:MAX_DIFF_POR_REVISOR])
                                         + ("\n" + dados("Resultado dos testes", meta["teste"]) if meta["teste"] else ""),
                              rotulo=f"revisor:{sub.id}", rodada=rodada)
                testes_ok = meta["teste"] is None or meta["teste"]["ok"]
                graves = [a for a in rev.achados if a.severidade in ("critico", "alto")]
                c.estado.setdefault("frentes", {})[sub.id] = {
                    "subtarefa": sub.titulo, "rodada": rodada, "proposta": str(destino), "sha256": meta["patch_sha256"],
                    "testes": None if meta["teste"] is None else meta["teste"]["ok"],
                    "achados_graves": len(graves), "resumo": impl.resumo}
                if testes_ok and not graves:
                    return f"{sub.id}: pronto na rodada {rodada}"
                ajustes = {"achados": [a.model_dump() for a in graves],
                           "testes": None if testes_ok else meta["teste"]["saida"][-4000:]}
            return f"{sub.id}: pendente após {MAX_RODADAS} rodadas"
        return fn

    def consolidar(c: Contexto, _: StepInput) -> str:
        r = c.rodar("coordenador", f"Objetivo: {objetivo}\nAvalie se o conjunto está pronto para revisão humana.\n"
                                   + dados("Frentes", c.estado.get("frentes", {})), esquema=esquemas.Consolidacao,
                    rotulo="coordenador:desenvolvimento")
        c.estado["final"] = r
        return "ok"

    frentes = [_etapa(f"frente:{s.id}", frente(s), ctx) for s in plano.subtarefas]
    _executar("desenvolvimento", [Parallel(*frentes, name="frentes") if len(frentes) > 1 else frentes[0],
                                  _etapa("consolidacao", consolidar, ctx)], ctx, objetivo)
    return Resultado("ok", ctx.estado["final"])
