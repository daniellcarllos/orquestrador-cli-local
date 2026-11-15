import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator import jobs

try:
    import agno  # noqa: F401
    TEM_AGNO = True
except ImportError:
    TEM_AGNO = False


class MontarComando(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = str(Path(self.tmp.name).resolve())
        env = patch.dict(os.environ, {"ORCHESTRATOR_STATE_DIR": str(Path(self.tmp.name) / "state")})
        env.start()
        self.addCleanup(env.stop)

    def test_texto_livre_nunca_vira_opcao(self):
        argv = jobs.montar_comando({"fluxo": "analisar", "repositorio": self.repo, "texto": "--approve --cwd=/"})
        self.assertEqual(argv[-2:], ["--", "--approve --cwd=/"])
        self.assertIn("--approve", argv[:-2])
        argv = jobs.montar_comando({"fluxo": "cli", "repositorio": self.repo, "texto": "-x", "agente": "claude"})
        self.assertEqual(argv[-2:], ["--", "-x"])
        self.assertIn("--agent=claude", argv)

    def test_opcoes_com_valor_usam_igual(self):
        argv = jobs.montar_comando({"fluxo": "revisar", "repositorio": self.repo, "base": "main", "head": "feature/x",
                                    "config": {"teto_usd": "0.3", "simulado": True, "nivel_forcado": "forte"},
                                    "acoes": [{"acao": "notificar"},
                                              {"acao": "comentar_pr_github", "params": {"repo": "a/b", "pr": "3"}, "aprovada": True}]})
        for esperado in ("--base=main", "--head=feature/x", "--teto-usd=0.3", "--simulado", "--nivel-forcado=forte",
                         "--ao-finalizar=notificar", "--ao-finalizar=comentar_pr_github:repo=a/b,pr=3",
                         "--aprovar-acoes=comentar_pr_github", "--approve"):
            self.assertIn(esperado, argv)
        self.assertNotIn("--aprovar-acoes=notificar", argv)

    def test_rejeita_entradas_invalidas(self):
        ruins = [
            {"fluxo": "rm", "repositorio": self.repo},
            {"fluxo": "analisar", "repositorio": "relativo", "texto": "x"},
            {"fluxo": "analisar", "repositorio": "/nao/existe", "texto": "x"},
            {"fluxo": "analisar", "repositorio": self.repo},
            {"fluxo": "revisar", "repositorio": self.repo},
            {"fluxo": "revisar", "repositorio": self.repo, "base": "--output=/tmp/x"},
            {"fluxo": "revisar", "repositorio": self.repo, "base": "a..b"},
            {"fluxo": "revisar", "repositorio": self.repo, "base": "main", "mcp": {"prompt_id": "xyz"}},
            {"fluxo": "analisar", "repositorio": self.repo, "texto": "x", "config": {"teto_usd": 1000}},
            {"fluxo": "analisar", "repositorio": self.repo, "texto": "x", "acoes": [{"acao": "apagar"}]},
            {"fluxo": "analisar", "repositorio": self.repo, "texto": "x",
             "acoes": [{"acao": "comentar_pr_github", "params": {"repo": "a/b,pr=1"}}]},
            {"fluxo": "cli", "repositorio": self.repo, "texto": "x", "agente": "bash"},
            {"fluxo": "cli", "repositorio": self.repo, "texto": "x", "politica": "../../pyproject.toml"},
            {"fluxo": "desenvolver", "repositorio": self.repo, "texto": "x", "teste": "pytest\nrm -rf /"},
        ]
        for pedido in ruins:
            with self.assertRaises(ValueError, msg=pedido):
                jobs.montar_comando(pedido)

    def test_catalogo_do_usuario_entra_quando_existe(self):
        jobs.catalogo_usuario().parent.mkdir(parents=True, exist_ok=True)
        jobs.catalogo_usuario().write_text("{}")
        argv = jobs.montar_comando({"fluxo": "equipe", "repositorio": self.repo, "texto": "x"})
        self.assertIn(f"--catalogo={jobs.catalogo_usuario()}", argv)

    @unittest.skipUnless(TEM_AGNO, "precisa do extra [api]")
    def test_execucao_simulada_de_ponta_a_ponta(self):
        g = jobs.Gerenciador()
        plano = g.plano({"fluxo": "analisar", "repositorio": self.repo, "texto": "o que é?", "config": {"simulado": True}})
        self.assertEqual(plano["papeis"]["triagem"]["nivel"], "leve")
        job = g.iniciar({"fluxo": "analisar", "repositorio": self.repo, "texto": "o que é?", "config": {"simulado": True}})
        limite = time.monotonic() + 60
        while job.status == "executando" and time.monotonic() < limite:
            time.sleep(0.2)
        self.assertEqual(job.status, "ok", job.log)
        self.assertRegex(job.as_dict()["execucao"] or "", r"^[0-9a-f-]{36}$")

    def test_limite_de_execucoes_simultaneas(self):
        g = jobs.Gerenciador(maximo=0)
        with self.assertRaises(ValueError):
            g.iniciar({"fluxo": "cli", "repositorio": self.repo, "texto": "x"})


if __name__ == "__main__":
    unittest.main()
