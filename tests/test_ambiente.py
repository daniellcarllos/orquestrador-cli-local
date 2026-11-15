import io
import os
import tempfile
import unittest
from pathlib import Path

from orchestrator import ambiente


class Ambiente(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arq = Path(self.tmp.name) / ".env"

    def escrever(self, texto, modo=0o600):
        self.arq.write_text(texto)
        os.chmod(self.arq, modo)

    def test_interpreta_formatos_comuns(self):
        v = ambiente.interpretar(
            "# comentário\nexport ANTHROPIC_API_KEY=sk-ant-x\nGOOGLE_API_KEY=\"com espaço\"\n"
            "OPENAI_API_KEY='aspas simples'\nMCP_PROMPTS_URL=https://h/mcp # fim\nminuscula=x\nSEM_IGUAL\n")
        self.assertEqual(v, {"ANTHROPIC_API_KEY": "sk-ant-x", "GOOGLE_API_KEY": "com espaço",
                             "OPENAI_API_KEY": "aspas simples", "MCP_PROMPTS_URL": "https://h/mcp"})

    def test_ambiente_do_terminal_tem_prioridade_e_vazios_sao_ignorados(self):
        self.escrever("ANTHROPIC_API_KEY=do-arquivo\nGOOGLE_API_KEY=g\nOPENAI_API_KEY=\n")
        env = {"ANTHROPIC_API_KEY": "do-terminal"}
        aplicados = ambiente.carregar(self.arq, env, io.StringIO())
        self.assertEqual(env, {"ANTHROPIC_API_KEY": "do-terminal", "GOOGLE_API_KEY": "g"})
        self.assertEqual(aplicados, ["GOOGLE_API_KEY"])

    def test_avisa_permissao_aberta_sem_mostrar_valores(self):
        self.escrever("ANTHROPIC_API_KEY=segredo-123\n", 0o644)
        avisos = io.StringIO()
        ambiente.carregar(self.arq, {}, avisos)
        self.assertIn("chmod 600", avisos.getvalue())
        self.assertNotIn("segredo-123", avisos.getvalue())

    def test_arquivo_ausente_ou_link_e_ignorado(self):
        self.assertEqual(ambiente.carregar(self.arq, {}, io.StringIO()), [])
        alvo = Path(self.tmp.name) / "outro"
        alvo.write_text("ANTHROPIC_API_KEY=x\n")
        self.arq.symlink_to(alvo)
        env = {}
        ambiente.carregar(self.arq, env, io.StringIO())
        self.assertEqual(env, {})


if __name__ == "__main__":
    unittest.main()
