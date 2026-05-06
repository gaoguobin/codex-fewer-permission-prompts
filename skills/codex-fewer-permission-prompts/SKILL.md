---
name: codex-fewer-permission-prompts
description: Codex permission prompts helper for safe prefix_rule proposals, execpolicy verification, dry-run apply, and rollback. Use for fewer permission prompts, Codex rules allowlist cleanup, or /fewer-permission-prompts doctor/propose/apply/verify/rollback.
---

Use this skill to reduce repeated approval prompts without weakening Codex's sandbox or approval model. Keep `approval_policy` and `sandbox_mode` intact; work only through official `.rules` files and `prefix_rule(...)`.

## Trigger Patterns

- Natural language: `减少 Codex 权限确认`, `生成低风险 rules 建议`, `清理/验证 Codex allow rules`
- Lifecycle: install, update, uninstall, doctor, status, scan, propose, apply, verify, rollback
- Slash-style text: `/fewer-permission-prompts doctor`, `/fewer-permission-prompts propose`, `/fewer-permission-prompts apply`, `/fewer-permission-prompts rollback`

Codex currently documents built-in slash commands only. Treat `/fewer-permission-prompts ...` as user text that this skill maps to the matching workflow; do not claim it registers a native Codex slash command.

## How To Execute

Prefer the installed module:

```powershell
python -m codex_fewer_permission_prompts doctor
python -m codex_fewer_permission_prompts status
python -m codex_fewer_permission_prompts scan
python -m codex_fewer_permission_prompts propose --dry-run
python -m codex_fewer_permission_prompts verify --rules-file $HOME\.codex\rules\default.rules
python -m codex_fewer_permission_prompts apply --rules-file $HOME\.codex\rules\default.rules
python -m codex_fewer_permission_prompts apply --rules-file $HOME\.codex\rules\default.rules --write
python -m codex_fewer_permission_prompts rollback --rules-file $HOME\.codex\rules\default.rules --remove-block
```

When running from the source repo before install, use the wrapper:

```powershell
python scripts\codex_fewer_permission_prompts.py doctor
```

When Codex loads this as a plugin skill and the Python package is not installed, use the bundled skill wrapper:

```powershell
python <skill-folder>\scripts\codex_fewer_permission_prompts.py doctor
```

The CLI also accepts `python -m codex_fewer_permission_prompts /fewer-permission-prompts doctor` as a slash-style compatibility form.

## Lifecycle

- Install: fetch and follow `.codex/INSTALL.md` from this repo.
- Update: fetch and follow `.codex/UPDATE.md`.
- Uninstall: fetch and follow `.codex/UNINSTALL.md`.
- After installing, updating, uninstalling, or changing rules, tell the user to restart Codex App or open a new CLI session so skill discovery or rules are reloaded.

## Safety Model

- Default to dry-run. Do not edit rules unless the user explicitly approves the apply step.
- Recommend only frequent, explainable, low-risk read-only or diagnostic command prefixes.
- Never recommend delete, move, write, install, registry, ACL, service, `git reset`, `git checkout`, `git clean`, `git push`, `git commit`, or complex shell script rules.
- Reject commands with redirection, variable expansion, wildcards, shell control flow, or sensitive path hints.
- Output only command summaries and counts. Do not print raw transcript text, secrets, tokens, or full conversation content.
- Before writing a `.rules` file, create a timestamped backup and update only the `codex-fewer-permission-prompts` sentinel block.

## Command Map

- `doctor` / `status`: locate `CODEX_HOME`, rules files, sessions, history, and logs; summarize JSONL shapes without printing content.
- `scan` / `analyze`: count observed shell commands from Codex session JSONL files.
- `propose`: classify observed commands and print candidate `prefix_rule(...)` entries with `match` and `not_match` examples.
- `verify`: run `codex execpolicy check --pretty --rules <rules-file> -- <command...>` for each generated or sentinel rule example.
- `apply`: show a unified diff by default. Add `--write` to ask for confirmation, back up the rules file, then append or replace the sentinel block. Use `--yes` only for controlled tests or when the user already approved the exact write.
- `rollback`: restore the latest backup, restore a named backup, or remove only the sentinel block.

If Codex official docs or local `codex execpolicy check` behavior disagree with this skill, treat the current official docs and local CLI behavior as the source of truth.
