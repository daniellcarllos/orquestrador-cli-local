import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from orchestrator import cli, core, mcp_prompts


class MCPPromptTests(unittest.TestCase):
    def setUp(self):
        self.id = "1234567890"
        self.payload = {"id": self.id, "titulo": "review", "conteudo": "guidance", "projeto": "P", "grupo": "G", "versao": 1}

    def test_parse_text_response_and_exact_scope(self):
        content = [SimpleNamespace(type="text", text=json.dumps(self.payload))]
        result = SimpleNamespace(is_error=False, structured_content=None, content=content)
        self.assertEqual(mcp_prompts.parse_result(result, self.id, "P", "G")["content"], "guidance")
        for project, group in [("wrong", "G"), ("P", "wrong")]:
            with self.assertRaises(ValueError):
                mcp_prompts.parse_result(result, self.id, project, group)

    def test_reject_urls_with_credentials_query_and_plain_http(self):
        for url in ("http://host/mcp", "https://u:p@host/mcp", "https://host/mcp?key=x"):
            with self.assertRaises(ValueError):
                mcp_prompts.validate_settings(url, "token", [self.id], "P", "G")

    def test_subprocess_does_not_receive_mcp_token(self):
        with patch.dict(os.environ, {"MCP_PROMPTS_TOKEN": "hidden-token"}):
            result = core.execute([sys.executable, "-c", "import os; print('MCP_PROMPTS_TOKEN' in os.environ)"], "", Path.cwd(), 5)
        self.assertEqual(result.stdout.strip(), "False")

    def test_run_requires_approval_before_mcp_read_and_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "diff.txt"
            file.write_text("diff", encoding="utf-8")
            args = ["run", "review", "--mcp-prompt-id", self.id, "--mcp-project", "P", "--mcp-group", "G", "--input-file", str(file)]
            with patch("orchestrator.cli.detect", return_value={"codex": "/fake"}), \
                 patch("orchestrator.mcp_prompts.fetch") as fetch, patch("orchestrator.cli.execute") as execute:
                self.assertEqual(cli.main(args), 2)
                self.assertEqual(cli.main([*args, "--approve"]), 2)
                fetch.assert_not_called()
                execute.assert_not_called()

    def test_review_sends_only_selected_context_to_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "diff.txt"
            file.write_text("diff sample", encoding="utf-8")
            docs = [{"id": self.id, "title": "review", "updated_at": None, "version": 1, "content": "guidance"}]
            result = core.Result(0, "review result", "", False, False)
            args = ["run", "review", "--mcp-prompt-id", self.id, "--mcp-project", "P", "--mcp-group", "G",
                    "--input-file", str(file), "--approve", "--approve-mcp"]
            with patch("orchestrator.cli.detect", return_value={"codex": "/fake"}), \
                 patch("orchestrator.mcp_prompts.fetch", return_value=docs) as fetch, \
                 patch("orchestrator.cli.execute", return_value=result) as execute, patch("orchestrator.cli.journal") as journal:
                self.assertEqual(cli.main(args), 0)
                fetch.assert_called_once_with([self.id], "P", "G")
                self.assertIn("diff sample", execute.call_args.args[1])
                self.assertIn("guidance", execute.call_args.args[1])
                self.assertNotIn("guidance", str(journal.call_args))

    def test_sdk_round_trip_in_memory_when_installed(self):
        try:
            from mcp import Client
            from mcp.server.mcpserver import MCPServer
        except ImportError:
            self.skipTest("SDK MCP opcional não instalado")
        server = MCPServer(name="local-test")
        payload = self.payload

        @server.tool()
        def ler_prompt(id: str) -> dict:
            return payload

        async def call():
            async with Client(server, raise_exceptions=True) as client:
                response = await client.call_tool("ler_prompt", {"id": self.id})
                return mcp_prompts.parse_result(response, self.id, "P", "G")

        self.assertEqual(asyncio.run(call())["content"], "guidance")

    def test_list_filters_project_group_and_exact_tag(self):
        entries = [
            {"id": "aaaaaaaaaa", "titulo": "ok", "grupo": "G", "projeto": "P", "tags": ["dotnet"]},
            {"id": "bbbbbbbbbb", "titulo": "other group", "grupo": "X", "projeto": "P", "tags": ["dotnet"]},
            {"id": "cccccccccc", "titulo": "other tag", "grupo": "G", "projeto": "P", "tags": ["other"]},
        ]
        result = SimpleNamespace(is_error=False, structured_content={"prompts": entries}, content=[])
        selected = mcp_prompts.parse_listing(result, "P", "G", "dotnet")
        self.assertEqual([x["id"] for x in selected], ["aaaaaaaaaa"])

    def test_list_follows_pagination_and_deduplicates(self):
        def page(ids, cursor):
            entries = [{"id": i, "titulo": i, "grupo": "G", "projeto": "P", "tags": ["t"]} for i in ids]
            return SimpleNamespace(is_error=False, structured_content={"prompts": entries, "proximo_cursor": cursor}, content=[])

        pages = [page(["aaaaaaaaaa", "bbbbbbbbbb"], "c1"), page(["bbbbbbbbbb", "cccccccccc"], "c2"), page(["dddddddddd"], None)]
        calls = []

        async def call(arguments):
            calls.append(arguments)
            return pages[len(calls) - 1]

        selected = asyncio.run(mcp_prompts.collect_pages(call, "P", "G", "t"))
        self.assertEqual([x["id"] for x in selected], ["aaaaaaaaaa", "bbbbbbbbbb", "cccccccccc", "dddddddddd"])
        self.assertEqual([c.get("cursor") for c in calls], [None, "c1", "c2"])
        self.assertTrue(all(c["limite"] == mcp_prompts.PAGE_SIZE and c["tag"] == "t" for c in calls))

    def test_list_rejects_stuck_or_endless_pagination(self):
        stuck = SimpleNamespace(is_error=False, structured_content={"prompts": [], "proximo_cursor": "same"}, content=[])

        async def call(arguments):
            return stuck

        with self.assertRaises(ValueError):
            asyncio.run(mcp_prompts.collect_pages(call, "P", "G", None))

    def test_list_command_requires_approval(self):
        with patch("orchestrator.mcp_prompts.list_metadata") as list_metadata:
            self.assertEqual(cli.main(["mcp-list", "--project", "P", "--group", "G"]), 2)
            list_metadata.assert_not_called()

    def test_tag_selection_uses_limit_and_checks_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "diff.txt"
            file.write_text("diff", encoding="utf-8")
            candidates = [{"id": "aaaaaaaaaa", "title": "context 1"}, {"id": "bbbbbbbbbb", "title": "context 2"}]
            docs = [{"id": self.id, "content": "review", "tags": []},
                    {"id": "aaaaaaaaaa", "content": "context 1", "tags": ["dotnet"]}]
            args = ["run", "review", "--mcp-prompt-id", self.id, "--mcp-project", "P", "--mcp-group", "G",
                    "--mcp-context-tag", "dotnet", "--mcp-max-contexts", "1", "--input-file", str(file), "--approve", "--approve-mcp"]
            with patch("orchestrator.cli.detect", return_value={"codex": "/fake"}), \
                 patch("orchestrator.mcp_prompts.list_metadata", return_value=candidates) as listing, \
                 patch("orchestrator.mcp_prompts.fetch", return_value=docs) as fetch, \
                 patch("orchestrator.cli.execute", return_value=core.Result(0, "ok", "", False, False)) as execute, \
                 patch("orchestrator.cli.journal"):
                self.assertEqual(cli.main(args), 0)
                listing.assert_called_once_with("P", "G", "dotnet")
                fetch.assert_called_once_with([self.id, "aaaaaaaaaa"], "P", "G")
                self.assertIn("context 1", execute.call_args.args[1])
                docs[1]["tags"] = ["removed"]
                self.assertEqual(cli.main(args), 2)
                self.assertEqual(execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
