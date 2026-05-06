# codex-fewer-permission-prompts

[![CI](https://github.com/gaoguobin/codex-fewer-permission-prompts/actions/workflows/ci.yml/badge.svg)](https://github.com/gaoguobin/codex-fewer-permission-prompts/actions/workflows/ci.yml)

Safely reduce repeated Codex permission prompts by turning frequent, low-risk
commands into reviewed Codex `prefix_rule(...)` suggestions.

This project is a Codex Agent Skill plus a small Python CLI. It scans local
Codex history for repeated read-only or diagnostic commands, proposes official
Codex rules, verifies the rules with `codex execpolicy check`, applies them only
after review, and can roll the changes back.

[Agent Skill](#agent-skill-and-discovery) · [Install](#install) · [Dry-run](#dry-run-and-propose) · [Apply](#apply) · [Verify](#verify) · [Rollback](#rollback) · [Safety](#safety-model) · [Plugin Readiness](#plugin-readiness) · [中文说明](#chinese)

## Why

Claude Code has `/fewer-permission-prompts`. Codex does not currently ship an
equivalent built-in command, but Codex does provide an official rules mechanism
for command prefixes. This repository keeps the workflow conservative:

1. scan local Codex JSONL history without printing conversation contents;
2. propose only explainable low-risk command prefixes;
3. verify `match` and `not_match` examples with Codex itself;
4. show a diff and require user approval before writing;
5. back up every touched rules file and support rollback.

It does not change Codex sandbox or approval settings.

## Highlights

| Capability | What it means |
| --- | --- |
| Official rule format | Generates Starlark `.rules` snippets with `prefix_rule(...)`. |
| Dry-run first | `propose` and default `apply` do not modify files. |
| Conservative classifier | Recommends read-only and diagnostic prefixes such as `git status`, `git diff`, `rg`, `codex --version`, and selected doctor/status commands. |
| Unsafe command rejection | Skips delete/write/install/system commands, dangerous Git operations, redirection, expansion, wildcards, and complex shell scripts. |
| Privacy-preserving scan | Outputs command summaries and counts, not raw prompts, responses, secrets, or complete transcripts. |
| Verification | Uses `codex execpolicy check --pretty --rules <file> -- <command...>` against each rule example. |
| Sentinel block | Writes only between `# BEGIN codex-fewer-permission-prompts` and `# END codex-fewer-permission-prompts`. |
| Rollback | Restores a backup or removes only the sentinel block. |

## Agent Skill and Discovery

This repository includes one Agent Skill:

| Skill name | Skill path | Purpose |
| --- | --- | --- |
| `codex-fewer-permission-prompts` | `skills/codex-fewer-permission-prompts/SKILL.md` | Help Codex scan repeated low-risk commands, propose safe `prefix_rule(...)` entries, verify them, apply them with backups, and roll them back. |

Tools that index public GitHub repositories for Agent Skills can discover the
skill at the path above. This project does not claim to be listed on SkillsMP or
any other marketplace, and it is not an official OpenAI plugin or official
marketplace project.

You can trigger the skill naturally:

```text
Generate safe Codex rules to reduce repeated permission prompts.
```

Or with slash-style text that the skill maps to its workflow:

```text
/fewer-permission-prompts
/fewer-permission-prompts doctor
/fewer-permission-prompts propose
/fewer-permission-prompts apply
/fewer-permission-prompts rollback
```

Codex currently documents built-in slash commands only. The slash-style text
above is handled by this skill and CLI; it does not register a native Codex
slash command.

Bare `/fewer-permission-prompts` is the default dry-run workflow: Codex should
run `doctor --json`, then `propose --dry-run`, summarize the proposed low-risk
rules, and stop without modifying files.

## Plugin Readiness

Codex documentation describes Skills as the reusable workflow authoring format
and Plugins as the installable distribution unit. This repository already
includes:

- `.codex-plugin/plugin.json`
- `skills/codex-fewer-permission-prompts/SKILL.md`
- `skills/codex-fewer-permission-prompts/scripts/codex_fewer_permission_prompts.py`

The plugin manifest points to `./skills/`, following the current Codex plugin
layout for bundled skills. Its plugin package name is `codex-permission-tools`
so it does not duplicate the bundled skill name. This metadata is preparatory
packaging and discovery metadata only. It does not install hooks, change Codex
config, change permissions, edit rules, or imply an official marketplace
listing.

Current supported installation remains the Codex-managed install flow below.

## Install

Paste this into Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/INSTALL.md
```

The install flow clones this repository to
`~/.codex/codex-fewer-permission-prompts`, installs the Python package in
editable user mode, copies the bundled skill into a standalone mirror at
`~/.codex/codex-fewer-permission-prompts-skill/codex-fewer-permission-prompts`,
and links that mirror into `~/.agents/skills/codex-fewer-permission-prompts`.

The source repo still contains plugin-ready metadata under `.codex-plugin`.
The user-facing skill path points outside that plugin repo so Codex skill menus
can show the single command label `Codex Fewer Permission Prompts` without the
plugin namespace prefix.

After installation, fully restart Codex App, or open a new Codex CLI process so
skill discovery refreshes. Once the app has restarted, use
`/fewer-permission-prompts` directly; opening a separate new chat is not
required. Do not judge `/` menu labels from the old app process that was running
during install.

## Doctor

Inspect the current Codex paths and available scan inputs:

```powershell
python -m codex_fewer_permission_prompts
python -m codex_fewer_permission_prompts doctor --json
```

`doctor` reports `CODEX_HOME`, the default rules file, whether the sentinel
block is present, and JSONL shape counts. It does not print transcript content.
With no CLI subcommand, the tool runs `doctor` followed by `propose --dry-run`.
If the current rules file already contains matching `prefix_rule(...)` entries,
dry-run omits those commands from the new candidate list so an installed rule is
not reported as if it still needs to be added.

## Dry-run and Propose

Generate candidate rules without modifying files:

```powershell
python -m codex_fewer_permission_prompts propose --dry-run
```

To write a machine-readable proposal:

```powershell
python -m codex_fewer_permission_prompts propose --dry-run --json
```

The generated rules include `match` and `not_match` examples so Codex can check
the intended behavior before loading or applying the rules.

To verify a dry-run proposal before applying it, write the proposal JSON and
verify it without `--rules-file`; the CLI will create a temporary rules file for
the check:

```powershell
python -m codex_fewer_permission_prompts propose --dry-run --json > proposal.json
python -m codex_fewer_permission_prompts verify --proposal-json proposal.json
```

Do not verify a dry-run proposal against the current `default.rules` unless the
rules have already been applied; positive examples are expected not to match
before then.

## Apply

Preview the planned diff only:

```powershell
python -m codex_fewer_permission_prompts apply --rules-file $HOME\.codex\rules\default.rules
```

Apply after review:

```powershell
python -m codex_fewer_permission_prompts apply --rules-file $HOME\.codex\rules\default.rules --write
```

`apply --write` asks for confirmation, creates a timestamped backup, then writes
the sentinel block. If the block already exists, only new uncovered candidates
are appended; existing managed rules are left unchanged.

After applying rules, restart Codex App or open a new CLI session so Codex
reloads `.rules` files.

## Verify

Check a rules file with Codex's own execpolicy evaluator:

```powershell
python -m codex_fewer_permission_prompts verify --rules-file $HOME\.codex\rules\default.rules
```

Every generated or sentinel rule should include examples that produce `match ok`
and `not_match ok`.

## Rollback

Remove only the sentinel block:

```powershell
python -m codex_fewer_permission_prompts rollback --rules-file $HOME\.codex\rules\default.rules --remove-block
```

Restore the latest backup:

```powershell
python -m codex_fewer_permission_prompts rollback --rules-file $HOME\.codex\rules\default.rules
```

Restore a named backup:

```powershell
python -m codex_fewer_permission_prompts rollback --rules-file $HOME\.codex\rules\default.rules --backup path\to\default.rules.bak.20260506-105718
```

After rollback, restart Codex App or open a new CLI session so Codex reloads
rules.

## Update

Paste this into Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/UPDATE.md
```

The update flow pulls the installed repository, reinstalls the editable Python
package, refreshes the standalone skill mirror, migrates legacy namespace-style
or repo-internal skill junctions to the standalone skill junction when needed,
and runs `doctor`.

After update, fully restart Codex App, or open a new Codex CLI process. Once the
app has restarted, use `/fewer-permission-prompts` directly. Do not use the
pre-restart app process to judge whether `/` menu labels have refreshed.

## Uninstall

Paste this into Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/UNINSTALL.md
```

The uninstall flow removes this tool's sentinel block from the default rules
file, uninstalls the Python package, removes the current or legacy skill
junction, deletes the standalone skill mirror, and deletes the installed
repository. It verifies the Python package uninstall and retries when editable
metadata remains. It preserves unrelated rules and unrelated skills.

## Safety Model

- Does not set `approval_policy = "never"`.
- Does not set `sandbox_mode = "danger-full-access"`.
- Does not edit Codex config, hooks, providers, model settings, API keys, or auth files.
- Does not auto-apply rules during scan or propose.
- Does not print raw prompts, responses, full conversations, API keys, tokens, or secrets.
- Does not recommend delete, move, write, install, registry, ACL, service, or high-risk Git commands.
- Writes only after a visible diff and explicit approval.
- Backs up the target `.rules` file before writing.
- Keeps all managed rules inside a sentinel block for review and removal.

The supported rule target is Codex's official `.rules` mechanism. If local Codex
CLI behavior differs from this README, treat the current Codex CLI and official
Codex documentation as the source of truth.

<a id="chinese"></a>

## 中文说明

`codex-fewer-permission-prompts` 是一个面向 Codex 的 Agent Skill 和 Python CLI，用来安全减少重复权限确认。
它不会关闭 Codex 的审批机制，也不会切到 `danger-full-access`；它只围绕 Codex 官方 `.rules` 文件生成、
验证、应用和回滚 `prefix_rule(...)`。

### Agent Skill 和可发现性

这个仓库包含一个 Agent Skill：

| Skill 名称 | Skill 路径 | 用途 |
| --- | --- | --- |
| `codex-fewer-permission-prompts` | `skills/codex-fewer-permission-prompts/SKILL.md` | 扫描本地 Codex 历史中的重复低风险命令，生成安全的 `prefix_rule(...)` 建议，验证、应用并支持回滚。 |

会索引公开 GitHub 仓库中 Agent Skills 的工具，可以通过上面的路径发现这个 skill。本项目不声称已经被
SkillsMP 或其它 marketplace 收录，也不声称是 OpenAI 官方 plugin 或官方 marketplace 项目。

可以用自然语言触发：

```text
生成 Codex 低风险 rules 建议，减少重复权限确认。
```

也可以用类 slash 文本触发：

```text
/fewer-permission-prompts
/fewer-permission-prompts doctor
/fewer-permission-prompts propose
/fewer-permission-prompts apply
/fewer-permission-prompts rollback
```

这里的 `/fewer-permission-prompts ...` 是这个 skill 和 CLI 识别的文本入口，不是 Codex 原生注册的
slash command。

裸 `/fewer-permission-prompts` 是默认 dry-run 流程：先跑 `doctor --json`，再跑 `propose --dry-run`，
总结候选低风险规则，然后停止，不修改文件。

### Plugin readiness

Codex 官方文档把 Skill 定义为可复用 workflow 的 authoring format，把 Plugin 定义为可安装的分发单元。
当前仓库已经包含 `.codex-plugin/plugin.json`，并且 manifest 指向 `./skills/`，方便后续按 Codex plugin
格式分发。

当前正式支持的安装方式仍然是下面的 Codex-managed 安装流程。这个 plugin metadata 只是为了发现和后续
打包准备，不会安装 hook、不会改 Codex 配置、不会改权限、不会写 rules，也不代表已经进入官方 marketplace。

### 安装

把这句话贴给 Codex：

```text
Fetch and follow instructions from https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/INSTALL.md
```

安装流程会把仓库克隆到 `~/.codex/codex-fewer-permission-prompts`，以 editable user 模式安装 Python
包，把内层 skill 复制到独立 mirror
`~/.codex/codex-fewer-permission-prompts-skill/codex-fewer-permission-prompts`，
再把这个 mirror 链接到 `~/.agents/skills/codex-fewer-permission-prompts`。

源码仓库仍然保留 `.codex-plugin` 作为 plugin-ready 元数据；用户实际加载的 skill 目录在 plugin
仓库外面。这样 Codex 的 skill 菜单可以只显示 `Codex Fewer Permission Prompts`，不带 plugin namespace 前缀。

安装后需要完全重启 Codex App，或新开 CLI 实例，让 Codex 重新扫描 skills。
重启后直接说 `/fewer-permission-prompts` 即可；不需要额外新开一个对话。不要用安装后尚未重启的旧
App 进程判断 `/` 菜单是否刷新，因为旧进程可能缓存安装前的 skill 菜单。

### Doctor

查看当前 Codex 路径、rules 文件和可扫描输入：

```powershell
python -m codex_fewer_permission_prompts
python -m codex_fewer_permission_prompts doctor --json
```

`doctor` 只输出 `CODEX_HOME`、默认 rules 文件、sentinel block 是否存在、JSONL shape 统计等信息，
不会打印完整历史对话内容。
CLI 不带子命令时，会先跑 `doctor`，再跑 `propose --dry-run`。
如果当前 rules 文件已经有能覆盖某条命令的 `prefix_rule(...)`，dry-run 会把它从新增候选中排除，
避免把已经生效的规则继续统计成“待添加”。

### Dry-run / propose

只生成候选规则，不修改文件：

```powershell
python -m codex_fewer_permission_prompts propose --dry-run
```

生成的规则会带 `match` 和 `not_match` 示例，方便后续用 Codex 自己的 execpolicy evaluator 验证。

如果要在应用前验证 dry-run 结果，先输出 proposal JSON，再不带 `--rules-file` 验证；CLI 会临时生成
候选 rules 文件：

```powershell
python -m codex_fewer_permission_prompts propose --dry-run --json > proposal.json
python -m codex_fewer_permission_prompts verify --proposal-json proposal.json
```

不要把未应用的 dry-run proposal 拿当前 `default.rules` 验正例；规则还没写入时，正例不命中是正常的。

### Apply

先只看计划 diff：

```powershell
python -m codex_fewer_permission_prompts apply --rules-file $HOME\.codex\rules\default.rules
```

确认后应用：

```powershell
python -m codex_fewer_permission_prompts apply --rules-file $HOME\.codex\rules\default.rules --write
```

`apply --write` 会先要求确认，再备份目标 `.rules` 文件。没有 sentinel block 时会创建；
已有 sentinel block 时只追加新的未覆盖候选，保留现有托管规则。应用后需要重启 Codex App 或新开 CLI session，让 rules
重新加载。

### Verify

用 Codex 官方 execpolicy evaluator 验证规则命中情况：

```powershell
python -m codex_fewer_permission_prompts verify --rules-file $HOME\.codex\rules\default.rules
```

每条生成规则都应该有 `match ok` 和 `not_match ok`。

### Rollback

只移除 sentinel block：

```powershell
python -m codex_fewer_permission_prompts rollback --rules-file $HOME\.codex\rules\default.rules --remove-block
```

或恢复最近备份：

```powershell
python -m codex_fewer_permission_prompts rollback --rules-file $HOME\.codex\rules\default.rules
```

回滚后也需要重启 Codex App 或新开 CLI session，让 rules 重新加载。

### 卸载

把这句话贴给 Codex：

```text
Fetch and follow instructions from https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/UNINSTALL.md
```

卸载流程会移除本工具的 sentinel block、Python 包、standalone skill mirror、skill junction 和安装仓库。
它会用 `pip show` 校验 Python 包是否仍存在，并在 editable metadata 残留时自动重试卸载；它不会删除无关
rules 或无关 skills。

### 行为边界

- 不设置 `approval_policy = "never"`。
- 不设置 `sandbox_mode = "danger-full-access"`。
- 不修改 Codex config、hooks、provider、model、API key 或 auth 文件。
- `scan` / `propose` 默认不写文件。
- 不输出 raw prompt、response、完整历史、API key、token 或 secret。
- 不推荐删除、移动、写文件、安装依赖、注册表、ACL、系统服务或高风险 Git 命令。
- 写入前展示 diff，并要求明确确认。
- 写入前备份目标 `.rules` 文件。
- 所有托管规则都放在 sentinel block 内，方便 review 和移除。

## Development

Install locally:

```powershell
python -m pip install --user -e .
```

Run checks:

```powershell
python -B -m unittest discover -s tests -v
python -B -m compileall -q src scripts tests skills\codex-fewer-permission-prompts\scripts
python -B scripts\check_metadata.py
python -B C:\Users\cedric.gao\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
python -B C:\Users\cedric.gao\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\codex-fewer-permission-prompts
git diff --check
```

GitHub Actions runs the same metadata, compile, unit, CLI, and wheel checks on
Windows and Linux for Python 3.9, 3.11, and 3.13.

Run against a test rules file before touching real Codex rules:

```powershell
python -m codex_fewer_permission_prompts apply --rules-file .\codex-fewer-permission-prompts-test.rules --yes
python -m codex_fewer_permission_prompts verify --rules-file .\codex-fewer-permission-prompts-test.rules
python -m codex_fewer_permission_prompts rollback --rules-file .\codex-fewer-permission-prompts-test.rules --remove-block --yes
```
