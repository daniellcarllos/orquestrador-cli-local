import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator import cli, core


class PolicyTests(unittest.TestCase):
    def test_explicit_and_default_selection(self):
        found = {"codex": "/x/codex", "claude": "/x/claude", "gemini": None}
        self.assertEqual(core.plan("analisar código", found).agent, "codex")
        self.assertEqual(core.plan("analisar código", found, "claude").agent, "claude")
        self.assertEqual(core.plan("revisar segurança", found).risk, "alto")

    def test_fail_closed_when_no_agent_or_invalid_override(self):
        with self.assertRaises(ValueError):
            core.plan("tarefa", {})
        with self.assertRaises(ValueError):
            core.plan("tarefa", {"codex": "/x"}, "gemini")

    def test_argv_modes(self):
        cwd = Path("/tmp")
        self.assertIn("read-only", core.command("codex", "/x", cwd))
        self.assertIn("--restricted", core.command("claude", "/x", cwd))
        self.assertIn("plan", core.command("gemini", "/x", cwd))
        self.assertNotIn("tarefa privada", core.command("codex", "/x", cwd))

    def test_approval_gate(self):
        with patch("orchestrator.cli.detect", return_value={"codex": "/x"}), patch("orchestrator.cli.execute") as execute:
            self.assertEqual(cli.main(["run", "teste", "--cwd", "."]), 2)
            execute.assert_not_called()


class ExecutionTests(unittest.TestCase):
    def test_input_output_redaction_and_failure(self):
        code = "import sys; t=sys.stdin.read(); print(t); print('api_key=abc',file=sys.stderr); sys.exit(3)"
        result = core.execute([sys.executable, "-c", code], "input", Path.cwd(), 5)
        self.assertEqual(result.exit_code, 3)
        self.assertIn("input", result.stdout)
        self.assertNotIn("abc", result.stderr)

    def test_timeout(self):
        result = core.execute([sys.executable, "-c", "import time; time.sleep(10)"], "", Path.cwd(), 1)
        self.assertTrue(result.timed_out)

    def test_output_limit(self):
        result = core.execute([sys.executable, "-c", "print('x'*1100000)"], "", Path.cwd(), 5)
        self.assertTrue(result.truncated)
        self.assertLessEqual(len(result.stdout), core.OUTPUT_LIMIT)

    def test_journal_has_restricted_permissions_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"ORCHESTRATOR_STATE_DIR": tmp}):
            cli.journal({"id": "test", "agent": "codex"})
            path = cli.history_path()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn('"agent": "codex"', path.read_text())


if __name__ == "__main__":
    unittest.main()
