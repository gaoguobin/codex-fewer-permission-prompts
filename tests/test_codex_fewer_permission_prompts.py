import json
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import codex_fewer_permission_prompts.cli as fewer_prompts
from codex_fewer_permission_prompts.cli import (
    BEGIN,
    END,
    SourceFile,
    classify,
    extract_commands_from_event,
    render_block,
    replace_sentinel,
    strip_sentinel,
    propose_candidates,
    CommandRecord,
    RuleCandidate,
    backup_file,
    cmd_apply,
    normalize_argv,
)


class ClassifierTests(unittest.TestCase):
    def test_allows_known_read_only_commands(self):
        for command in [
            "git status --short --branch",
            "git diff -- README.md",
            "git log -1 --oneline",
            "rg prefix_rule",
            "Get-Content notes.txt",
            "Get-ChildItem .",
            "codex --version",
            "codex mcp list",
            "python -m codex_fast_proxy status",
            "python -m codex_fast_proxy doctor",
        ]:
            with self.subTest(command=command):
                self.assertTrue(classify(command).safe)

    def test_rejects_dangerous_commands(self):
        for command in [
            "rm -rf build",
            "Remove-Item file.txt",
            "git reset --hard",
            "git checkout main",
            "git clean -xfd",
            "git push",
            "git commit -m test",
            "npm install",
            "python -m pip install x",
            "Get-Content $HOME/.codex/auth.json",
            "git status > out.txt",
        ]:
            with self.subTest(command=command):
                self.assertFalse(classify(command).safe)


class ParserTests(unittest.TestCase):
    def test_extracts_codex_shell_command(self):
        event = {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell_command",
                "arguments": json.dumps({"command": "git status --short"}),
            },
        }
        source = SourceFile(Path("sample.jsonl"), "codex_session")
        records = extract_commands_from_event(event, source)
        self.assertEqual(records[0].command, "git status --short")


class RuleBlockTests(unittest.TestCase):
    def test_replace_and_strip_sentinel(self):
        records = [
            CommandRecord("git status --short", "codex_session", Path("a.jsonl")),
            CommandRecord("git status --short", "codex_session", Path("b.jsonl")),
        ]
        candidates = propose_candidates(records, None, min_count=2, max_candidates=5, shell_wrapper="none")
        block = render_block(candidates)
        self.assertIn(BEGIN, block)
        self.assertIn(END, block)
        original = "prefix_rule(pattern=[\"codex\", \"--version\"], decision=\"allow\")\n"
        updated = replace_sentinel(original, block)
        self.assertIn(original.strip(), updated)
        self.assertIn(BEGIN, updated)
        stripped, removed = strip_sentinel(updated)
        self.assertTrue(removed)
        self.assertIn(original.strip(), stripped)
        self.assertNotIn(BEGIN, stripped)

    def test_apply_shape_uses_match_and_not_match(self):
        records = [
            CommandRecord("codex --version", "codex_session", Path("a.jsonl")),
            CommandRecord("codex --version", "codex_session", Path("b.jsonl")),
        ]
        candidates = propose_candidates(records, None, min_count=2, max_candidates=5, shell_wrapper="none")
        block = render_block(candidates)
        self.assertIn("match =", block)
        self.assertIn("not_match =", block)
        self.assertIn('pattern = ["codex", "--version"]', block)

    def test_apply_defaults_to_dry_run(self):
        candidate = RuleCandidate(
            command="codex --version",
            count=2,
            source_kinds=("test",),
            pattern=("codex", "--version"),
            family="codex-version",
            reason="Codex version check",
            match=("codex --version",),
            not_match=("codex login",),
        )
        args = SimpleNamespace(rules_file="default.rules", write=False, yes=False)
        output = StringIO()
        with patch.object(fewer_prompts, "load_or_generate_candidates", return_value=[candidate]):
            with patch.object(fewer_prompts, "backup_file", side_effect=AssertionError("backup should not run")):
                with patch.object(Path, "write_text", side_effect=AssertionError("write should not run")):
                    with redirect_stdout(output):
                        status = cmd_apply(args)
        self.assertEqual(status, 0)
        self.assertIn("Dry-run only", output.getvalue())

    def test_backup_file_creates_missing_parent(self):
        root = Path("test-backup-parent")
        target = root / "rules" / "default.rules"
        try:
            backup = backup_file(target)
            self.assertTrue(backup.exists())
            self.assertTrue(target.parent.exists())
        finally:
            for path in sorted(root.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            if root.exists():
                root.rmdir()

    def test_slash_alias_defaults_to_dry_run_propose(self):
        self.assertEqual(normalize_argv(["/fewer-permission-prompts"]), ["propose", "--dry-run"])
        self.assertEqual(normalize_argv(["/fpp", "doctor"]), ["doctor"])


class PackagingTests(unittest.TestCase):
    def test_plugin_skill_matches_root_skill(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(
            (root / "SKILL.md").read_text(encoding="utf-8"),
            (root / "skills" / "codex-fewer-permission-prompts" / "SKILL.md").read_text(encoding="utf-8"),
        )

    def test_plugin_manifest_points_to_skills(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "codex-permission-tools")
        self.assertEqual(manifest["skills"], "./skills/")

    def test_plugin_skill_has_script_wrapper(self):
        root = Path(__file__).resolve().parents[1]
        wrapper = root / "skills" / "codex-fewer-permission-prompts" / "scripts" / "codex_fewer_permission_prompts.py"
        self.assertTrue(wrapper.exists())


if __name__ == "__main__":
    unittest.main()
