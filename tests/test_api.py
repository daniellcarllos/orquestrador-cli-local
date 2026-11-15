"""Orquestração por API com modelo simulado: sem rede, sem chave, sem custo."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import agno  # noqa: F401
    import pydantic  # noqa: F401
    TEM_AGNO = True
except ImportError:
    TEM_AGNO = False

from orchestrator.api import custos, modelos, segredos
from orchestrator.api.ferramentas import AcessoNegado, Repositorio, dividir_diff, filtrar_diff


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class EstadoIsolado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        env = patch.dict(os.environ, {"ORCHESTRATOR_STATE_DIR": str(self.raiz / "state")})
        env.start()
        self.addCleanup(env.stop)


class CatalogoECustos(unittest.TestCase):
    def catalogo(self):
        c = modelos.carregar()
        c["alternativos"]["leve"] = [{"provedor": "google", "modelo": "gemini-leve"}]
        c["precos_por_milhao"]["claude-haiku-5-5"] = {"entrada": 1.0, "saida": 5.0}
        return modelos.validar(c)

    def test_catalogo_exemplo_valido_e_rejeita_invalidos(self):
        c = self.catalogo()
        for estrago in ({"niveis": {}}, {"versao": 1}):
            with self.assertRaises(ValueError):
                modelos.validar({**c, **estrago})
        ruim = json.loads(json.dumps(c))
        ruim["niveis"]["leve"]["provedor"] = "desconhecido"
        with self.assertRaises(ValueError):
            modelos.validar(ruim)

    def test_escolhe_pelo_provedor_com_chave_e_falha_sem_nenhum(self):
        c = self.catalogo()
        self.assertEqual(modelos.escolher(c, "leve", {"ANTHROPIC_API_KEY": "x"}).modelo, "claude-haiku-5-5")
        self.assertEqual(modelos.escolher(c, "leve", {"GOOGLE_API_KEY": "x"}).modelo, "gemini-leve")
        with self.assertRaises(ValueError):
            modelos.escolher(c, "forte", {"GOOGLE_API_KEY": "x"})
        self.assertEqual(modelos.escolher(c, "forte", {}, simulado=True).modelo, "claude-opus-5-5")

    def test_custo_e_teto(self):
        p = custos.preco(self.catalogo(), "claude-haiku-5-5")
        self.assertEqual(custos.custo(1_000_000, 200_000, p), 2.0)
        self.assertIsNone(custos.preco(self.catalogo(), "claude-opus-5-5"))
        o = custos.Orcamento(0.10, teto_tokens=1000)
        o.registrar("m", 500, 0.08)
        with self.assertRaises(custos.TetoExcedido):
            o.verificar(0.05)
        with self.assertRaises(custos.TetoExcedido):
            o.verificar(None, 600)
        o.registrar("sem-preco", 10, None)
        self.assertEqual(o.resumo()["modelos_sem_preco"], ["sem-preco"])
        with self.assertRaises(custos.TetoExcedido):
            custos.Orcamento(1.0, gasto_dia_usd=4.9, teto_dia_usd=5.0).verificar(0.2)

    def test_gasto_do_dia_soma_so_api_de_hoje(self):
        from datetime import datetime, timezone
        agora = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
        entradas = [{"modo": "api", "started_at": "2026-11-15T01:00:00+00:00", "custo_usd": 0.2},
                    {"modo": "api", "started_at": "2026-11-14T23:00:00+00:00", "custo_usd": 9},
                    {"started_at": "2026-11-15T02:00:00+00:00", "custo_usd": 9}]
        self.assertEqual(custos.gasto_do_dia(entradas, agora), 0.2)


class SegredosEFerramentas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / "src").mkdir()
        (self.repo / "src" / "app.py").write_text("x = 1\nAPI_KEY=abc123\nsenha=xpto\n")
        (self.repo / ".env").write_text("SEGREDO=1")
        (self.repo / "chave.pem").write_text("-----BEGIN PRIVATE KEY-----\nzz\n-----END PRIVATE KEY-----")
        (self.repo / "bin.dat").write_bytes(b"\0\1\2")
        os.symlink("/etc", self.repo / "fora")
        self.r = Repositorio(self.repo)

    def test_redacao(self):
        texto = "sk-ant-" + "a" * 30 + " AIza" + "b" * 35 + " ghp_" + "c" * 36 + " Authorization: Bearer xyz"
        limpo = segredos.redigir(texto)
        for vazado in ("aaaaaaaaaa", "bbbbbbbbbb", "cccccccccc", "xyz"):
            self.assertNotIn(vazado, limpo)

    def test_leitura_limitada_ao_repositorio(self):
        self.assertIn("x = 1", self.r.ler_arquivo("src/app.py"))
        self.assertNotIn("abc123", self.r.ler_arquivo("src/app.py"))
        for caminho in ("../../etc/passwd", ".env", "chave.pem", "bin.dat", "fora/hosts", "/etc/passwd"):
            with self.assertRaises((AcessoNegado, ValueError), msg=caminho):
                self.r.ler_arquivo(caminho)
        lista = self.r.listar_arquivos()
        self.assertIn("src/app.py", lista)
        self.assertNotIn(".env", lista)
        self.assertNotIn("chave.pem", lista)
        self.assertIn("src/app.py:1", self.r.buscar_texto("x = 1"))

    def test_diff_filtra_arquivos_sensiveis(self):
        diff = ("diff --git a/a.py b/a.py\n+ok\n"
                "diff --git a/.env b/.env\n+SEGREDO=1\n"
                "diff --git a/k.pem b/k.pem\n+chave\n")
        limpo = filtrar_diff(diff)
        self.assertIn("a.py", limpo)
        self.assertNotIn("SEGREDO", limpo)
        self.assertNotIn("k.pem", limpo)
        self.assertEqual(list(dividir_diff(limpo)), ["a.py"])

    def test_git_diff_rejeita_referencia_maliciosa(self):
        for ref in ("--output=/tmp/x", "a;rm", "a b"):
            with self.assertRaises(ValueError):
                self.r.git_diff(ref)


@unittest.skipUnless(TEM_AGNO, "instale o extra [api] para testar os fluxos")
class Fluxos(EstadoIsolado):
    def contexto(self, responder=None, teto=0.5, repo=None):
        from orchestrator.api import agentes, registro
        from orchestrator.api.simulado import ModeloSimulado

        cat = modelos.carregar()
        cat["precos_por_milhao"]["claude-sonnet-5-5"] = {"entrada": 3.0, "saida": 15.0}
        ex = registro.Execucao("teste", "tarefa")
        return agentes.Contexto(cat, custos.Orcamento(teto), ex, repo, ModeloSimulado(responder))

    def padrao(self, papel, mensagens, esquema):
        from orchestrator.api.simulado import exemplo_de_schema
        return json.dumps(exemplo_de_schema(esquema.model_json_schema())) if esquema else "ok"

    def test_revisao_paralela_consolida_e_registra_custo_por_agente(self):
        from orchestrator.api import fluxos

        threads = set()

        def lento(papel, msgs, esquema):
            threads.add(threading.get_ident())
            time.sleep(0.2)
            return self.padrao(papel, msgs, esquema)

        ctx = self.contexto(lento)
        inicio = time.monotonic()
        r = fluxos.revisar(ctx, "diff --git a/a.py b/a.py\n+x = 1\n")
        duracao = time.monotonic() - inicio
        papeis = [e.papel for e in ctx.execucao.etapas]
        self.assertEqual(papeis[0], "triagem")
        self.assertEqual(set(papeis[1:4]), {"revisor:seguranca", "revisor:bugs", "revisor:qualidade"})
        self.assertEqual(papeis[4], "coordenador:revisao")
        self.assertLess(duracao, 0.2 * 5 - 0.2, "os revisores deveriam rodar em paralelo")
        self.assertGreaterEqual(len(threads), 3)
        niveis = {e.papel: (e.nivel, e.modelo) for e in ctx.execucao.etapas}
        self.assertEqual(niveis["triagem"][0], "leve")
        self.assertEqual(niveis["revisor:bugs"][0], "medio")
        self.assertEqual(niveis["coordenador:revisao"][0], "forte")
        self.assertIsNotNone(next(e for e in ctx.execucao.etapas if e.papel == "revisor:bugs").custo_usd)
        self.assertIn("Revisão de código", fluxos.revisao_markdown(r.saida))

    def test_seguranca_escala_para_forte_quando_risco_alto(self):
        from orchestrator.api import fluxos

        def resp(papel, msgs, esquema):
            if papel == "triagem":
                return json.dumps({"tipo": "revisao", "complexidade": "media", "risco": "alto", "areas": [], "justificativa": "auth"})
            return self.padrao(papel, msgs, esquema)

        ctx = self.contexto(resp)
        fluxos.revisar(ctx, "diff --git a/a.py b/a.py\n+x\n")
        niveis = {e.papel: e.nivel for e in ctx.execucao.etapas}
        self.assertEqual(niveis["revisor:seguranca"], "forte")
        self.assertEqual(niveis["revisor:bugs"], "medio")

    def test_resposta_fora_do_formato_interrompe_antes_da_consolidacao(self):
        from orchestrator.api import fluxos

        ctx = self.contexto(lambda p, m, e: "lixo" if p == "revisor:bugs" else self.padrao(p, m, e))
        with self.assertRaises(fluxos.FluxoInterrompido):
            fluxos.revisar(ctx, "diff --git a/a.py b/a.py\n+x\n")
        status = {e.papel: e.status for e in ctx.execucao.etapas}
        self.assertEqual(status["revisor:bugs"], "fora_do_contrato")
        self.assertNotIn("coordenador:revisao", status)

    def test_teto_interrompe_sem_chamar_o_modelo(self):
        from orchestrator.api import fluxos

        chamadas = []
        ctx = self.contexto(lambda p, m, e: chamadas.append(p) or self.padrao(p, m, e), teto=0.0000001)
        with self.assertRaises(fluxos.FluxoInterrompido):
            fluxos.revisar(ctx, "diff --git a/a.py b/a.py\n" + "+x\n" * 30000)
        self.assertNotIn("revisor:bugs", chamadas)

    def test_conteudo_nao_confiavel_vai_marcado_e_redigido(self):
        from orchestrator.api import fluxos

        vistos = []

        def resp(papel, msgs, esquema):
            vistos.append("\n".join(str(m.content) for m in msgs))
            return self.padrao(papel, msgs, esquema)

        fluxos.revisar(self.contexto(resp), "diff --git a/a.py b/a.py\n+token = 'sk-ant-" + "z" * 30 + "'\n")
        prompt_revisor = next(v for v in vistos if "Foco desta revisão" in v)
        self.assertIn("<dados>", prompt_revisor)
        self.assertNotIn("z" * 30, "".join(vistos))

    def _repo_dev(self, teste: str) -> Path:
        repo = self.raiz / "repo"
        repo.mkdir()
        (repo / "a.py").write_text("def a():\n    return 0\n")
        (repo / "b.py").write_text("def b():\n    return 0\n")
        (repo / "test_ab.py").write_text("import unittest\nfrom a import a\nfrom b import b\n\n"
                                         "class T(unittest.TestCase):\n    def test(self):\n" + teste)
        git(repo, "init", "-q")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "base")
        return repo

    def _resp_dev(self, pedidos: list):
        def resp(papel, msgs, esquema):
            if papel == "planejador":
                return json.dumps({"objetivo": "ajustar", "riscos": [], "subtarefas": [
                    {"id": "sub-a", "titulo": "a", "descricao": "a retorna 1", "arquivos": ["a.py"], "criterios_aceite": []},
                    {"id": "sub-b", "titulo": "b", "descricao": "b retorna 2", "arquivos": ["b.py"], "criterios_aceite": []}]})
            if papel.startswith("implementador:"):
                pedidos.append((papel, "\n".join(str(m.content) for m in msgs)))
                sub = papel.split(":")[1]
                nome, valor = ("a.py", 1) if sub == "sub-a" else ("b.py", 2)
                return json.dumps({"subtarefa": sub, "resumo": "feito",
                                   "arquivos": [{"caminho": nome, "conteudo": f"def {nome[0]}():\n    return {valor}\n"}]})
            if papel.startswith("revisor:"):
                return json.dumps({"foco": "patch", "achados": [], "observacoes": ""})
            return self.padrao(papel, msgs, esquema)
        return resp

    def test_desenvolvimento_paralelo_gera_patches_testados_em_copia(self):
        from orchestrator.api import fluxos
        from orchestrator.api.ferramentas import Repositorio

        repo = self._repo_dev("        self.assertIn(a(), (0, 1))\n        self.assertIn(b(), (0, 2))\n")
        ctx = self.contexto(self._resp_dev([]), repo=Repositorio(repo))
        r = fluxos.desenvolver(ctx, "a retorna 1 e b retorna 2", f"{sys.executable} -m unittest -q")
        frentes = ctx.estado["frentes"]
        self.assertEqual(set(frentes), {"sub-a", "sub-b"})
        for f in frentes.values():
            self.assertIn("+    return", (Path(f["proposta"]) / "changes.patch").read_text())
            self.assertEqual((f["rodada"], f["testes"]), (1, True))
        self.assertEqual((repo / "a.py").read_text(), "def a():\n    return 0\n", "a origem não pode mudar")
        self.assertIsNotNone(r.saida)

    def test_teste_falhando_gera_rodada_de_ajuste_com_o_erro(self):
        from orchestrator.api import fluxos
        from orchestrator.api.ferramentas import Repositorio

        # exige as duas mudanças juntas: em cada cópia isolada o teste falha
        repo = self._repo_dev("        self.assertEqual((a(), b()), (1, 2))\n")
        pedidos = []
        ctx = self.contexto(self._resp_dev(pedidos), repo=Repositorio(repo))
        fluxos.desenvolver(ctx, "a retorna 1 e b retorna 2", f"{sys.executable} -m unittest -q")
        for f in ctx.estado["frentes"].values():
            self.assertEqual((f["rodada"], f["testes"]), (fluxos.MAX_RODADAS, False))
        segunda = [texto for papel, texto in pedidos if papel == "implementador:sub-a"][1]
        self.assertIn("Ajustes pedidos pela revisão anterior", segunda)
        self.assertIn("AssertionError", segunda)

    def test_plano_com_arquivo_compartilhado_e_recusado(self):
        from orchestrator.api import esquemas, fluxos

        plano = esquemas.PlanoDesenvolvimento(objetivo="x", subtarefas=[
            esquemas.Subtarefa(id="a", titulo="a", descricao="a", arquivos=["x.py"]),
            esquemas.Subtarefa(id="b", titulo="b", descricao="b", arquivos=["x.py"])])
        with self.assertRaises(ValueError):
            fluxos._validar_plano(plano)
        plano.subtarefas[1].arquivos = [".env"]
        with self.assertRaises(ValueError):
            fluxos._validar_plano(plano)

    def test_implementador_fora_dos_arquivos_permitidos_e_barrado(self):
        from orchestrator.api import esquemas, fluxos

        repo = self.raiz / "r2"
        repo.mkdir()
        (repo / "a.py").write_text("x\n")
        git(repo, "init", "-q")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "base")
        sub = esquemas.Subtarefa(id="a", titulo="a", descricao="a", arquivos=["a.py"])
        impl = esquemas.Implementacao(subtarefa="a", resumo="", arquivos=[esquemas.ArquivoAlterado(caminho="outro.py", conteudo="y")])
        with self.assertRaises(AcessoNegado):
            fluxos._aplicar_em_copia(repo, "HEAD", sub, impl, self.raiz / "p", None)

    def test_equipe_registra_lider(self):
        from orchestrator.api import equipe

        ctx = self.contexto()
        self.assertTrue(equipe.executar(ctx, "Explique o projeto"))
        self.assertEqual(ctx.execucao.etapas[-1].papel, "lider")
        self.assertEqual(ctx.execucao.etapas[-1].nivel, "forte")

    def test_historico_sem_conteudo_da_tarefa(self):
        from orchestrator.cli import history_path

        ctx = self.contexto()
        ctx.execucao.tarefa_resumo = "SEGREDO-DA-TAREFA"
        ctx.rodar("triagem", "algo")
        ctx.execucao.finalizar("ok", ctx.orcamento.resumo())
        linha = history_path().read_text()
        self.assertNotIn("SEGREDO-DA-TAREFA", linha)
        self.assertIn('"modo": "api"', linha)
        self.assertEqual(oct((ctx.execucao.pasta / "meta.json").stat().st_mode & 0o777), "0o600")


class Acoes(unittest.TestCase):
    def test_externa_sem_aprovacao_fica_pendente_e_local_executa(self):
        from orchestrator.api import acoes

        chamadas = []
        with patch.dict(acoes.EXECUTORES, {"comentar_pr_github": lambda t, a: chamadas.append(t) or "ok",
                                           "notificar": lambda t, a: "ok"}):
            r = acoes.executar(acoes.interpretar(["notificar", "comentar_pr_github:repo=a/b,pr=1"]), "texto",
                               set(), entrada=lambda: "não")
        self.assertEqual([x["status"] for x in r], ["ok", "pendente"])
        self.assertEqual(chamadas, [])

    def test_aprovada_por_flag_ou_sim_executa_com_texto_redigido(self):
        from orchestrator.api import acoes

        enviados = []
        with patch.dict(acoes.EXECUTORES, {"comentar_pr_azure": lambda t, a: enviados.append(t) or "ok"}):
            pedido = acoes.interpretar(["comentar_pr_azure:org=o,projeto=p,repo=r,pr=3"])
            acoes.executar(pedido, "achado com sk-ant-" + "q" * 30, {"comentar_pr_azure"})
            acoes.executar(pedido, "segundo", set(), entrada=lambda: "SIM")
        self.assertEqual(len(enviados), 2)
        self.assertNotIn("q" * 30, enviados[0])

    def test_parametros_invalidos(self):
        from orchestrator.api import acoes

        for esp in ("apagar_tudo", "comentar_pr_github:repo", "comentar_pr_github:X=1"):
            with self.assertRaises(ValueError):
                acoes.interpretar([esp])
        with self.assertRaises(ValueError):
            acoes.comentar_pr_github("t", {"repo": "a/b", "pr": "1; rm"})


if __name__ == "__main__":
    unittest.main()
