import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator import capabilities, cli, core


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.policy = {"version": "v1", "tiers": {
            "simples": [{"agent": "gemini", "model": "fast-model"}],
            "média": [{"agent": "codex", "model": "code-model"}],
            "alta": [{"agent": "claude", "model": "strong-model"}],
        }}
        self.available = {"gemini": "/g", "codex": "/c", "claude": "/a"}

    def test_routes_complexity_to_policy_agent_and_model(self):
        for task, agent, model in [("formatar texto", "gemini", "fast-model"),
                                   ("implementar código", "codex", "code-model"),
                                   ("revisar segurança", "claude", "strong-model")]:
            result = core.plan(task, self.available, policy=self.policy)
            self.assertEqual((result.agent, result.model, result.usage), (agent, model, "desconhecido"))

    def test_claude_example_selects_light_for_simple_and_strong_for_review_and_planning(self):
        policy = core.load_policy(Path(__file__).resolve().parent.parent / "examples" / "policies" / "policy.claude.example.json")
        for task, expected_model, category in [("formatar um texto", "haiku", "geral"),
                                                ("implementar código", "sonnet", "código"),
                                                ("planejar arquitetura", "opus", "planejamento"),
                                                ("conferir implementação", "opus", "conferência"),
                                                ("revisar código", "opus", "conferência")]:
            result = core.plan(task, self.available, policy=policy)
            self.assertEqual((result.agent, result.model, result.task_type), ("claude", expected_model, category))

    def test_fail_closed_when_policy_unavailable_or_override_not_authorized(self):
        with self.assertRaises(ValueError):
            core.plan("formatar", {"codex": "/c"}, policy=self.policy)
        with self.assertRaises(ValueError):
            core.plan("formatar", self.available, "claude", self.policy)

    def test_model_in_all_cli_commands_and_no_shell(self):
        for agent in core.AGENTS:
            command = core.command(agent, "/bin/fake", Path("/tmp"), model="model-1")
            self.assertEqual(command[command.index("--model") + 1], "model-1")

    def test_policy_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "policy.json"
            file.write_text(json.dumps(self.policy), encoding="utf-8")
            self.assertEqual(core.load_policy(file), self.policy)
            self.policy["tiers"]["alta"][0]["model"] = "--not-a-model"
            file.write_text(json.dumps(self.policy), encoding="utf-8")
            with self.assertRaises(ValueError):
                core.load_policy(file)

    def test_real_execution_blocked_when_model_flag_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "policy.json"
            file.write_text(json.dumps(self.policy), encoding="utf-8")
            with patch("orchestrator.cli.detect", return_value=self.available), \
                 patch("orchestrator.cli.capabilities.inspect", return_value={"model_flag": None}), \
                 patch("orchestrator.cli.execute") as execute:
                self.assertEqual(cli.main(["run", "formatar", "--policy", str(file), "--approve"]), 2)
                execute.assert_not_called()

    def test_selected_model_reaches_approved_cli_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "policy.json"
            file.write_text(json.dumps(self.policy), encoding="utf-8")
            result = core.Result(0, "ok", "", False, False)
            with patch("orchestrator.cli.detect", return_value=self.available), \
                 patch("orchestrator.cli.capabilities.inspect", return_value={"model_flag": True}), \
                 patch("orchestrator.cli.execute", return_value=result) as execute, \
                 patch("orchestrator.cli.journal"):
                self.assertEqual(cli.main(["run", "formatar", "--policy", str(file), "--approve"]), 0)
                argv = execute.call_args.args[0]
                self.assertEqual(argv[0], "/g")
                self.assertEqual(argv[argv.index("--model") + 1], "fast-model")

    def test_capability_inventory_from_actual_help_shape(self):
        version = core.Result(0, "cli 1.2.3\n", "", False, False)
        help_result = core.Result(0, "--model --output-format --sandbox --resume", "", False, False)
        with patch("orchestrator.capabilities.execute", side_effect=[version, help_result]):
            inventory = capabilities.inspect("gemini", "/g", Path.cwd())
        self.assertEqual(inventory["version"], "1.2.3")
        self.assertTrue(inventory["model_flag"])
        self.assertEqual(inventory["token_usage"], "não verificado")


if __name__ == "__main__":
    unittest.main()
