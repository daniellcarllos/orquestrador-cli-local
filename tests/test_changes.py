import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator import changes, cli, core


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "code.txt").write_text("original\n")
        (self.source / ".env.production").write_text("sensitive")
        changes.init_copy(self.source)

    def make_proposal(self):
        base = changes.validate_source(self.source)
        copy = self.root / "copy"
        copy.mkdir()
        changes.copy_tracked(self.source, copy)
        self.assertFalse((copy / ".env.production").exists())
        changes.init_copy(copy)
        (copy / "code.txt").write_text("alterado\n")
        (copy / "novo.txt").write_text("novo\n")
        proposal = self.root / "proposal"
        meta = changes.export_patch(copy, proposal, base)
        return proposal, meta

    def test_review_then_apply(self):
        proposal, meta = self.make_proposal()
        self.assertEqual((self.source / "code.txt").read_text(), "original\n")
        changes.apply(self.source, proposal, meta["patch_sha256"])
        self.assertEqual((self.source / "code.txt").read_text(), "alterado\n")
        self.assertEqual((self.source / "novo.txt").read_text(), "novo\n")
        self.assertEqual((self.source / ".env.production").read_text(), "sensitive")

    def test_modified_patch_and_wrong_approval_rejected(self):
        proposal, meta = self.make_proposal()
        with self.assertRaises(ValueError):
            changes.apply(self.source, proposal, "0" * 64)
        (proposal / "changes.patch").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            changes.apply(self.source, proposal, meta["patch_sha256"])

    def test_dirty_source_rejected(self):
        proposal, meta = self.make_proposal()
        (self.source / "untracked.txt").write_text("user content")
        with self.assertRaises(ValueError):
            changes.apply(self.source, proposal, meta["patch_sha256"])

    def test_symlink_rejected(self):
        base = changes.validate_source(self.source)
        copy = self.root / "copy"
        copy.mkdir()
        changes.copy_tracked(self.source, copy)
        changes.init_copy(copy)
        (copy / "link").symlink_to("code.txt")
        with self.assertRaises(ValueError):
            changes.export_patch(copy, self.root / "proposal", base)

    def test_prepare_gate_and_end_to_end_with_mocked_agent(self):
        proposal = self.root / "proposal"

        def mock_execute(argv, task, cwd, timeout):
            (cwd / "code.txt").write_text("agent change\n")
            return core.Result(0, "", "", False, False)

        args = ["prepare", "tarefa", "--cwd", str(self.source), "--output", str(proposal)]
        with patch("orchestrator.cli.detect", return_value={"codex": "/fake"}), \
             patch("orchestrator.cli.execute", side_effect=mock_execute) as execute:
            self.assertEqual(cli.main(args), 2)
            execute.assert_not_called()
            self.assertEqual(cli.main([*args, "--approve"]), 0)
        self.assertEqual((self.source / "code.txt").read_text(), "original\n")
        digest = __import__("hashlib").sha256((proposal / "changes.patch").read_bytes()).hexdigest()
        self.assertEqual(cli.main(["apply", str(proposal), "--cwd", str(self.source), "--approve-sha256", digest]), 0)
        self.assertEqual((self.source / "code.txt").read_text(), "agent change\n")

    def test_reject_proposal_inside_source_via_symlink(self):
        alias = self.root / "alias"
        alias.symlink_to(self.source, target_is_directory=True)
        args = ["prepare", "tarefa", "--cwd", str(self.source), "--output", str(alias / "proposal"), "--approve"]
        with patch("orchestrator.cli.detect", return_value={"codex": "/fake"}), \
             patch("orchestrator.cli.execute") as execute:
            self.assertEqual(cli.main(args), 2)
            execute.assert_not_called()

    def test_prepare_claude_uses_restricted_file_tools(self):
        proposal = self.root / "claude-proposal"

        def mock_execute(argv, task, cwd, timeout):
            self.assertEqual(argv[0], "/fake-claude")
            self.assertIn("--restricted", argv)
            self.assertIn("--strict-mcp-config", argv)
            self.assertIn("acceptEdits", argv)
            self.assertIn("Read,Edit,Write,Glob,Grep", argv)
            self.assertNotIn("Bash", " ".join(argv))
            (cwd / "code.txt").write_text("claude change\n")
            return core.Result(0, "", "", False, False)

        args = ["prepare", "tarefa", "--agent", "claude", "--cwd", str(self.source),
                "--output", str(proposal), "--approve"]
        with patch("orchestrator.cli.detect", return_value={"claude": "/fake-claude"}), \
             patch("orchestrator.cli.execute", side_effect=mock_execute):
            self.assertEqual(cli.main(args), 0)
        self.assertEqual((self.source / "code.txt").read_text(), "original\n")
        self.assertIn("claude change", (proposal / "changes.patch").read_text())

    def test_prepare_claude_missing_fails_without_agent_execution(self):
        args = ["prepare", "tarefa", "--agent", "claude", "--cwd", str(self.source),
                "--output", str(self.root / "proposal"), "--approve"]
        with patch("orchestrator.cli.detect", return_value={"claude": None}), \
             patch("orchestrator.cli.execute") as execute:
            self.assertEqual(cli.main(args), 2)
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
