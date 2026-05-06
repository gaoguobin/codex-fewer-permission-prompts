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
- Standalone skill mirror: `%USERPROFILE%\.codex\codex-fewer-permission-prompts-skill\codex-fewer-permission-prompts`
- Skill junction: `%USERPROFILE%\.agents\skills\codex-fewer-permission-prompts -> %USERPROFILE%\.codex\codex-fewer-permission-prompts-skill\codex-fewer-permission-prompts`

The source repo keeps `.codex-plugin/plugin.json` for plugin-ready metadata.
The user skill junction points to a standalone mirror outside that plugin repo
so the Codex skill menu can show a single entry such as
`Codex Fewer Permission Prompts`, without the plugin namespace prefix.

This install does not edit Codex rules. The first real rules write happens only when the user later approves `apply --write`.

## Install steps

If the Codex environment uses sandbox or approval controls, request approval/escalation for the install block because it clones from GitHub, installs a Python package, writes under `%USERPROFILE%\.codex`, and creates a junction under `%USERPROFILE%\.agents`.

If any command fails because of network, permissions, sandbox write limits, or junction creation, do not try unrelated workarounds. Ask for approval and rerun the same intended install step.

Run this PowerShell block exactly:

```powershell
$repoRoot = Join-Path $HOME '.codex\codex-fewer-permission-prompts'
$skillMirrorRoot = Join-Path $HOME '.codex\codex-fewer-permission-prompts-skill'
$skillMirror = Join-Path $skillMirrorRoot 'codex-fewer-permission-prompts'
$skillsRoot = Join-Path $HOME '.agents\skills'
$skillLink = Join-Path $skillsRoot 'codex-fewer-permission-prompts'
$legacyNamespace = Join-Path $skillsRoot 'codex-permission-tools'
$sourceSkill = Join-Path $repoRoot 'skills\codex-fewer-permission-prompts'

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git is required before installing codex-fewer-permission-prompts.'
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'python is required before installing codex-fewer-permission-prompts.'
}

if (Test-Path $repoRoot) {
    throw 'codex-fewer-permission-prompts is already installed. Follow UPDATE.md instead.'
}

if (Test-Path $skillLink) {
    throw 'The skill junction already exists. Remove it or follow UNINSTALL.md before reinstalling.'
}

if (Test-Path $legacyNamespace) {
    throw 'The legacy codex-permission-tools skill namespace already exists. Follow UPDATE.md to migrate it or UNINSTALL.md before reinstalling.'
}

if (Test-Path $skillMirrorRoot) {
    throw 'The standalone skill mirror already exists. Follow UPDATE.md to refresh it or UNINSTALL.md before reinstalling.'
}

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null
git clone https://github.com/gaoguobin/codex-fewer-permission-prompts.git $repoRoot
python -m pip install --user -e $repoRoot

if (-not (Test-Path (Join-Path $sourceSkill 'SKILL.md'))) {
    throw "Bundled skill is missing: $sourceSkill"
}

New-Item -ItemType Directory -Force -Path $skillMirrorRoot | Out-Null
Copy-Item -LiteralPath $sourceSkill -Destination $skillMirrorRoot -Recurse -Force
cmd /d /c "mklink /J `"$skillLink`" `"$skillMirror`""
```

## After install

Run this check in the same Codex turn:

```powershell
python -m codex_fewer_permission_prompts doctor --json
```

Report the JSON result in the reply. When the command succeeds, explicitly tell the user:

```text
请完全重启 Codex App，或新开 CLI 实例，让它重新扫描 ~/.agents/skills；重启后直接说“/fewer-permission-prompts”即可开始默认 dry-run 流程。不要用安装后尚未重启的旧 App 进程判断 / 菜单是否已刷新，因为旧进程可能缓存安装前的 skill 列表。
```

Do not claim the skill is available before restarting Codex App or opening a
fresh CLI process.

After restarting Codex App or opening a new CLI process, the user can ask:

- `/fewer-permission-prompts`
- `/fewer-permission-prompts doctor`
- `/fewer-permission-prompts propose`
- `/fewer-permission-prompts apply`
- `生成 Codex 低风险 rules 建议`
- `回滚 codex-fewer-permission-prompts 规则`

## Existing install

If the repository already exists, fetch and follow:

- `https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/UPDATE.md`
