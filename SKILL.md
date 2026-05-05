---
name: codex-fewer-permission-prompts
description: Safely reduce repeated Codex permission prompts by scanning Codex session history for frequent low-risk shell commands, proposing official prefix_rule entries, verifying them with codex execpolicy check, applying them with backups and sentinel blocks, and rolling them back. Use when the user asks for fewer permission prompts, Codex rules suggestions, smart allow rules, execpolicy allowlist cleanup, or a Codex-native alternative to Claude Code /fewer-permission-prompts.
---

# Codex Fewer Permission Prompts

Use this skill to reduce repeated approval prompts without weakening Codex's sandbox or approval model. Keep `approval_policy` and `sandbox_mode` intact; work only through official `.rules` files and `prefix_rule(...)`.

## Workflow

Run the bundled Python script from this skill folder:

```bash
python scripts/codex_fewer_permission_prompts.py doctor
python scripts/codex_fewer_permission_prompts.py propose --dry-run
python scripts/codex_fewer_permission_prompts.py verify --rules-file ~/.codex/rules/default.rules
python scripts/codex_fewer_permission_prompts.py apply --rules-file ~/.codex/rules/default.rules --write
python scripts/codex_fewer_permission_prompts.py rollback --rules-file ~/.codex/rules/default.rules
```

On Windows PowerShell, use the same script path with backslashes.

## Safety Rules

- Default to dry-run. Do not edit rules unless the user explicitly approves the apply step.
- Recommend only frequent, explainable, low-risk read-only or diagnostic command prefixes.
- Never recommend delete, move, write, install, registry, ACL, service, `git reset`, `git checkout`, `git clean`, `git push`, `git commit`, or complex shell script rules.
- Reject commands with redirection, variable expansion, wildcards, shell control flow, or sensitive path hints.
- Output only command summaries and counts. Do not print raw transcript text, secrets, tokens, or full conversation content.
- Before writing a `.rules` file, create a timestamped backup and update only the `codex-fewer-permission-prompts` sentinel block.
- After changing rules, tell the user to restart Codex App or start a new CLI session so rules are reloaded.

## Commands

- `doctor`: locate `CODEX_HOME`, rules files, sessions, history, and logs; summarize JSONL shapes without printing content.
- `analyze`: count observed shell commands from Codex session JSONL files.
- `propose`: classify observed commands and print candidate `prefix_rule(...)` entries with `match` and `not_match` examples.
- `verify`: run `codex execpolicy check --pretty --rules <rules-file> -- <command...>` for each generated or sentinel rule example.
- `apply`: show a unified diff by default. Add `--write` to ask for confirmation, back up the rules file, then append or replace the sentinel block.
- `rollback`: restore the latest backup or remove the sentinel block.

If Codex official docs or local `codex execpolicy check` behavior disagree with this skill, treat the current official docs and local CLI behavior as the source of truth.
