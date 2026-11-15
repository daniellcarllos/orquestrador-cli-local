"""Comandos de terminal da orquestração por API. Importado só quando um desses comandos é usado."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

COMANDOS = ("analisar", "revisar", "desenvolver", "equipe", "custos", "comparar", "acao", "api-doctor", "limpar")
TETO_PADRAO = float(os.environ.get("ORCHESTRATOR_TETO_USD", "0.50"))


def registrar_parser(commands) -> None:
    def comuns(p, repo_obrigatorio=False):
        p.add_argument("--cwd", type=Path, default=None if not repo_obrigatorio else Path.cwd(),
                       help="Repositório que os agentes podem ler")
        p.add_argument("--catalogo", type=Path, help="Catálogo de modelos (padrão: examples/api/modelos.json)")
        p.add_argument("--teto-usd", type=float, default=TETO_PADRAO, help="Gasto máximo desta execução em US$")
        p.add_argument("--teto-tokens", type=int, default=400_000, help="Limite de tokens desta execução")
        p.add_argument("--teto-dia-usd", type=float, default=None, help="Gasto máximo do dia em US$")
        p.add_argument("--nivel-forcado", choices=("leve", "medio", "forte"),
                       help="Usa o mesmo nível em todas as etapas (para comparar custo)")
        p.add_argument("--simulado", action="store_true", help="Modelo simulado: sem chave e sem custo")
        p.add_argument("--ao-finalizar", action="append", default=[], metavar="ACAO[:k=v,...]",
                       help="Ação ao terminar (notificar, comentar_pr_azure, comentar_pr_github, salvar_na_biblioteca)")
        p.add_argument("--aprovar-acoes", action="append", default=[], metavar="ACAO",
                       help="Aprova de antemão uma ação com efeito externo")
        p.add_argument("--approve", action="store_true", help="Autoriza as chamadas aos modelos e o gasto")
        p.add_argument("--json", action="store_true", help="Imprime o resultado em JSON")
        p.add_argument("--so-plano", action="store_true", help="Só imprime o plano (JSON) e sai, sem custo")
        p.add_argument("--resumo-arquivo", type=Path, help=argparse.SUPPRESS)  # usado pelo painel

    p = commands.add_parser("analisar", help="Análise de código por área, em paralelo, com consolidação")
    p.add_argument("pergunta")
    p.add_argument("--max-areas", type=int, default=4)
    comuns(p, True)

    p = commands.add_parser("revisar", help="Code review com revisores em paralelo (segurança, bugs, qualidade)")
    p.add_argument("--base", help="Branch ou commit base (diff base...head do repositório)")
    p.add_argument("--head", default="HEAD")
    p.add_argument("--diff", type=Path, help="Arquivo de diff em vez de usar git")
    p.add_argument("--mcp-prompt-id", help="Diretrizes de revisão da biblioteca MCP")
    p.add_argument("--mcp-project")
    p.add_argument("--mcp-group")
    comuns(p, True)

    p = commands.add_parser("desenvolver", help="Planeja, implementa em paralelo, testa e revisa (gera patches)")
    p.add_argument("objetivo")
    p.add_argument("--teste", help="Comando de teste a rodar em cada cópia (ex.: 'pytest -q')")
    p.add_argument("--max-subtarefas", type=int, default=4)
    comuns(p, True)

    p = commands.add_parser("equipe", help="Time do Agno: líder forte delega para membros mais baratos")
    p.add_argument("tarefa")
    p.add_argument("--modo", choices=("coordinate", "route", "broadcast"), default="coordinate")
    comuns(p)

    p = commands.add_parser("custos", help="Gasto e tokens das execuções por API")
    p.add_argument("--dias", type=int, default=7)

    p = commands.add_parser("comparar", help="Compara custo, tokens e tempo de duas execuções")
    p.add_argument("execucao_a")
    p.add_argument("execucao_b")

    p = commands.add_parser("acao", help="Executa (ou repete) uma ação sobre o resultado de uma execução")
    p.add_argument("execucao")
    p.add_argument("acao", metavar="ACAO[:k=v,...]")
    p.add_argument("--aprovar-acoes", action="append", default=[])

    commands.add_parser("api-doctor", help="Provedores configurados, catálogo e versão do Agno")

    p = commands.add_parser("limpar", help="Remove pastas de execução antigas")
    p.add_argument("--dias", type=int, default=30)


def _erro(msg: str) -> int:
    print(f"Erro: {msg}", file=sys.stderr)
    return 2


def _dependencias() -> None:
    try:
        import agno  # noqa: F401
        import pydantic  # noqa: F401
    except ImportError:
        raise ValueError("Orquestração por API indisponível: instale com `pip install '.[api]'` num ambiente virtual.")


def _plano(args, catalogo) -> dict:
    from . import modelos
    from .agentes import PAPEIS

    papeis = {}
    for nome, papel in PAPEIS.items():
        nivel = args.nivel_forcado or papel.nivel
        try:
            papeis[nome] = modelos.escolher(catalogo, nivel, simulado=args.simulado).as_dict()
        except ValueError as exc:
            papeis[nome] = {"nivel": nivel, "erro": str(exc)}
    return {"comando": args.action, "simulado": args.simulado, "teto_usd": args.teto_usd,
            "teto_tokens": args.teto_tokens, "papeis": papeis,
            "acoes": args.ao_finalizar, "repositorio": str(args.cwd.resolve()) if args.cwd else None}


def executar(args: argparse.Namespace) -> int:
    from .. import cli as base

    try:
        if args.action == "limpar":
            from . import registro

            print(f"{registro.limpar(args.dias)} pastas removidas.")
            return 0
        if args.action == "custos":
            return _custos(base, args.dias)
        if args.action == "comparar":
            return _comparar(args.execucao_a, args.execucao_b)
        _dependencias()
        if args.action == "api-doctor":
            return _doctor()
        if args.action == "acao":
            return _acao(args)
        return _fluxo(base, args)
    except (ValueError, OSError) as exc:
        return _erro(str(exc))


def _doctor() -> int:
    import importlib.metadata as md

    from . import modelos

    catalogo = modelos.carregar()
    print(json.dumps({"agno": md.version("agno"), "provedores": modelos.provedores_configurados(),
                      "catalogo": catalogo["versao"], "niveis": catalogo["niveis"],
                      "precos_configurados": sorted(k for k, v in catalogo.get("precos_por_milhao", {}).items()
                                                    if v["entrada"] is not None),
                      "nota": "As chaves não são exibidas. Preços nulos: custo em US$ não é calculado nem limitado."},
                     ensure_ascii=False, indent=2))
    return 0


def _fluxo(base, args) -> int:
    from . import acoes, agentes, custos, fluxos, modelos, registro
    from .ferramentas import Repositorio
    from .simulado import ModeloSimulado

    catalogo = modelos.carregar(args.catalogo)
    pedidos = acoes.interpretar(args.ao_finalizar)
    plano = _plano(args, catalogo)
    if args.so_plano:
        print(json.dumps(plano, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(plano, ensure_ascii=False, indent=2), file=sys.stderr, flush=True)
    if not args.approve:
        print("Execução não iniciada: use --approve após revisar papéis, modelos e teto.", file=sys.stderr)
        return 2
    if not args.simulado:
        faltando = [p for p, v in plano["papeis"].items() if "erro" in v]
        if faltando:
            raise ValueError(plano["papeis"][faltando[0]]["erro"])

    repo = Repositorio(args.cwd) if args.cwd else None
    historico = []
    try:
        from ..painel.web import read_history

        historico = read_history(5000)
    except Exception:
        pass
    orcamento = custos.Orcamento(args.teto_usd, args.teto_tokens, custos.gasto_do_dia(historico), args.teto_dia_usd)
    resumo_tarefa = getattr(args, "pergunta", None) or getattr(args, "objetivo", None) or getattr(args, "tarefa", None) or "revisão"
    execucao = registro.Execucao(args.action, resumo_tarefa if not args.simulado else f"[simulado] {resumo_tarefa}")
    ctx = agentes.Contexto(catalogo, orcamento, execucao, repo, ModeloSimulado() if args.simulado else None,
                           args.nivel_forcado)
    execucao.progresso_ativo = True
    _resumo(args, {"execucao": execucao.id, "status": "executando"})

    status, texto, estruturado = "ok", "", None
    try:
        if args.action == "revisar":
            diff = _obter_diff(args, repo)
            if args.mcp_prompt_id:
                from .. import mcp_prompts

                if not args.mcp_project or not args.mcp_group:
                    raise ValueError("Informe --mcp-project e --mcp-group junto com --mcp-prompt-id.")
                doc = mcp_prompts.fetch([args.mcp_prompt_id], args.mcp_project, args.mcp_group)[0]
                ctx.instrucoes_extra["revisor"] = doc["content"]
                ctx.instrucoes_extra["coordenador"] = doc["content"]
            r = fluxos.revisar(ctx, diff)
            estruturado, texto = r.saida, fluxos.revisao_markdown(r.saida)
        elif args.action == "analisar":
            if not 1 <= args.max_areas <= 8:
                raise ValueError("--max-areas deve estar entre 1 e 8.")
            r = fluxos.analisar(ctx, args.pergunta, args.max_areas)
            estruturado, texto = r.saida, fluxos.analise_markdown(r.saida)
        elif args.action == "desenvolver":
            if not 1 <= args.max_subtarefas <= 6:
                raise ValueError("--max-subtarefas deve estar entre 1 e 6.")
            r = fluxos.desenvolver(ctx, args.objetivo, args.teste, args.max_subtarefas)
            estruturado = {"consolidacao": r.saida.model_dump(), "frentes": ctx.estado.get("frentes", {})}
            texto = _desenvolvimento_markdown(r.saida, ctx.estado.get("frentes", {}))
        elif args.action == "equipe":
            from . import equipe

            texto = equipe.executar(ctx, args.tarefa, args.modo)
    except (fluxos.FluxoInterrompido, custos.TetoExcedido, RuntimeError, ValueError) as exc:
        status, texto = "interrompido", f"# Execução interrompida\n\n{exc}\n"
    except KeyboardInterrupt:
        status, texto = "cancelado", "# Execução cancelada pelo usuário\n"

    execucao.salvar("resultado.md", texto)
    if estruturado is not None:
        execucao.salvar("resultado.json", estruturado.model_dump() if hasattr(estruturado, "model_dump") else estruturado)
    if pedidos and status == "ok":
        execucao.acoes = acoes.executar(pedidos, texto, set(args.aprovar_acoes))
    meta = execucao.finalizar(status, orcamento.resumo())

    _resumo(args, {"execucao": execucao.id, "status": status, "custo_usd": meta.get("custo_usd"),
                   "tokens": meta.get("tokens"), "acoes": execucao.acoes})
    print(texto)
    resumo = {"execucao": execucao.id, "status": status, "pasta": str(execucao.pasta), **orcamento.resumo(),
              "etapas": len(execucao.etapas), "acoes": execucao.acoes}
    print(json.dumps(meta if args.json else resumo, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0 if status == "ok" else 1


def _resumo(args, dados: dict) -> None:
    """Arquivo lido pelo painel para acompanhar a execução (só metadados)."""
    if getattr(args, "resumo_arquivo", None):
        args.resumo_arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def _obter_diff(args, repo) -> str:
    from .ferramentas import filtrar_diff

    if args.diff:
        caminho = args.diff.resolve(strict=True)
        if not caminho.is_file() or caminho.stat().st_size > 400_000:
            raise ValueError("O diff deve ser um arquivo de até 400 KB.")
        return filtrar_diff(caminho.read_text(encoding="utf-8", errors="replace"))
    if not args.base:
        raise ValueError("Informe --base (comparar branches) ou --diff (arquivo).")
    return repo.git_diff(args.base, args.head)


def _desenvolvimento_markdown(consolidacao, frentes: dict) -> str:
    linhas = [f"# Desenvolvimento em paralelo\n\n{consolidacao.resumo}\n",
              f"**Pronto para revisão humana:** {'sim' if consolidacao.pronto_para_revisao_humana else 'não'}\n",
              "\n## Frentes\n"]
    for sid, f in frentes.items():
        testes = {True: "passaram", False: "falharam", None: "não executados"}[f["testes"]]
        linhas.append(f"- **{sid}** ({f['subtarefa']}): rodada {f['rodada']}, testes {testes}, "
                      f"{f['achados_graves']} achados graves")
        linhas.append(f"  - Proposta: `{f['proposta']}`")
        linhas.append(f"  - Aplicar após revisar: `python3 -m orchestrator apply {f['proposta']} --cwd <repo> --approve-sha256 {f['sha256']}`")
    if consolidacao.pendencias:
        linhas.append("\n## Pendências\n\n" + "\n".join(f"- {p}" for p in consolidacao.pendencias))
    return "\n".join(linhas) + "\n"


def _custos(base, dias: int) -> int:
    from datetime import datetime, timedelta, timezone

    from ..painel.web import read_history

    limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    entradas = [e for e in read_history(5000) if e.get("modo") == "api" and str(e.get("started_at", "")) >= limite]
    por_modelo: dict[str, dict] = {}
    por_fluxo: dict[str, dict] = {}
    for e in entradas:
        f = por_fluxo.setdefault(e.get("action", "?"), {"execucoes": 0, "custo_usd": 0.0, "tokens": 0})
        f["execucoes"] += 1
        f["custo_usd"] = round(f["custo_usd"] + (e.get("custo_usd") or 0), 6)
        f["tokens"] += e.get("tokens") or 0
        for etapa in e.get("etapas", []):
            m = por_modelo.setdefault(etapa["modelo"], {"chamadas": 0, "tokens": 0, "custo_usd": 0.0})
            m["chamadas"] += 1
            m["tokens"] += etapa["tokens_entrada"] + etapa["tokens_saida"]
            m["custo_usd"] = round(m["custo_usd"] + (etapa.get("custo_usd") or 0), 6)
    print(json.dumps({"dias": dias, "execucoes": len(entradas),
                      "custo_total_usd": round(sum(e.get("custo_usd") or 0 for e in entradas), 6),
                      "por_fluxo": por_fluxo, "por_modelo": por_modelo}, ensure_ascii=False, indent=2))
    return 0


def _comparar(a: str, b: str) -> int:
    from . import registro

    ma, mb = registro.ler(a), registro.ler(b)

    def resumo(m):
        etapas = m.get("etapas", [])
        return {"fluxo": m.get("action"), "status": m.get("status"), "custo_usd": m.get("custo_usd"),
                "tokens": m.get("tokens"), "duracao_ms": m.get("duration_ms"), "chamadas": len(etapas),
                "modelos": sorted({e["modelo"] for e in etapas})}

    ra, rb = resumo(ma), resumo(mb)
    reducao = None
    if ra["custo_usd"] and rb["custo_usd"]:
        reducao = round((1 - rb["custo_usd"] / ra["custo_usd"]) * 100, 1)
    elif ra["tokens"] and rb["tokens"]:
        reducao = round((1 - rb["tokens"] / ra["tokens"]) * 100, 1)
    print(json.dumps({"a": ra, "b": rb, "reducao_percentual_de_b_sobre_a": reducao,
                      "base_da_reducao": "custo" if ra["custo_usd"] and rb["custo_usd"] else "tokens"},
                     ensure_ascii=False, indent=2))
    return 0


def _acao(args) -> int:
    from . import acoes, registro

    meta = registro.ler(args.execucao)
    texto = (registro.pasta_execucoes() / args.execucao / "resultado.md").read_text(encoding="utf-8")
    resultados = acoes.executar(acoes.interpretar([args.acao]), texto, set(args.aprovar_acoes))
    print(json.dumps({"execucao": meta["id"], "acoes": resultados}, ensure_ascii=False, indent=2))
    return 0 if all(r["status"] == "ok" for r in resultados) else 1
