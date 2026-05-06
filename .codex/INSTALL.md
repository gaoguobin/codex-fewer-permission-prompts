# codex-fewer-permission-prompts install for Codex

Use these instructions when an engineer asks Codex to install or enable the Codex fewer permission prompts skill.

## One-paste prompt for engineers

Paste this into Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/INSTALL.md
```

## What this installs

- Git repo: `%USERPROFILE%\.codex\codex-fewer-permission-prompts`
- Python package: editable user install of `codex-fewer-permission-prompts`
- Skill namespace junction: `%USERPROFILE%\.agents\skills\codex-permission-tools -> %USERPROFILE%\.codex\codex-fewer-permission-prompts\skills`

The outer namespace is intentionally `codex-permission-tools`, while the bundled
skill remains `codex-fewer-permission-prompts`. This avoids a duplicated Codex
skill menu label such as `Codex Fewer Permission Prompts: Codex Fewer Permission
Prompts`.

This install does not edit Codex rules. The first real rules write happens only when the user later approves `apply --write`.

## Install steps

If the Codex environment uses sandbox or approval controls, request approval/escalation for the install block because it clones from GitHub, installs a Python package, writes under `%USERPROFILE%\.codex`, and creates a junction under `%USERPROFILE%\.agents`.

If any command fails because of network, permissions, sandbox write limits, or junction creation, do not try unrelated workarounds. Ask for approval and rerun the same intended install step.

Run this PowerShell block exactly:

```powershell
$repoRoot = Join-Path $HOME '.codex\codex-fewer-permission-prompts'
$skillsRoot = Join-Path $HOME '.agents\skills'
$skillNamespace = Join-Path $skillsRoot 'codex-permission-tools'
$legacySkillNamespace = Join-Path $skillsRoot 'codex-fewer-permission-prompts'
$skillTarget = Join-Path $repoRoot 'skills'

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git is required before installing codex-fewer-permission-prompts.'
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'python is required before installing codex-fewer-permission-prompts.'
}

if (Test-Path $repoRoot) {
    throw 'codex-fewer-permission-prompts is already installed. Follow UPDATE.md instead.'
}

if (Test-Path $skillNamespace) {
    throw 'The skill junction already exists. Remove it or follow UNINSTALL.md before reinstalling.'
}

if (Test-Path $legacySkillNamespace) {
    throw 'The legacy codex-fewer-permission-prompts skill namespace already exists. Follow UPDATE.md to migrate it or UNINSTALL.md before reinstalling.'
}

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null
git clone https://github.com/gaoguobin/codex-fewer-permission-prompts.git $repoRoot
python -m pip install --user -e $repoRoot
cmd /d /c "mklink /J `"$skillNamespace`" `"$skillTarget`""
```

## After install

Run this check in the same Codex turn:

```powershell
python -m codex_fewer_permission_prompts doctor --json
```

Report the JSON result in the reply. When the command succeeds, explicitly tell the user:

```text
请重启 Codex App 并回到这个对话，或新开 CLI 实例，让它重新扫描 ~/.agents/skills；然后再说“/fewer-permission-prompts doctor”或“生成 Codex 低风险规则建议”。
```

Do not claim the skill is available before the restart.

After restarting Codex App or opening a new CLI process, the user can ask:

- `/fewer-permission-prompts doctor`
- `/fewer-permission-prompts propose`
- `/fewer-permission-prompts apply`
- `生成 Codex 低风险 rules 建议`
- `回滚 codex-fewer-permission-prompts 规则`

## Existing install

If the repository already exists, fetch and follow:

- `https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/UPDATE.md`
