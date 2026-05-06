# codex-fewer-permission-prompts update for Codex

Use these instructions when an engineer asks Codex to update the Codex fewer permission prompts skill.

## One-paste prompt for engineers

```text
Fetch and follow instructions from https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/UPDATE.md
```

## Update steps

If the Codex environment uses sandbox or approval controls, request approval/escalation for the update block because it fetches from GitHub, installs a Python package, may write under `%USERPROFILE%\.codex`, and may create a junction under `%USERPROFILE%\.agents`.

If any command fails because of network, permissions, sandbox write limits, or junction creation, do not try unrelated workarounds. Ask for approval and rerun the same intended update step.

Run this PowerShell block exactly:

```powershell
$repoRoot = Join-Path $HOME '.codex\codex-fewer-permission-prompts'
$skillsRoot = Join-Path $HOME '.agents\skills'
$skillNamespace = Join-Path $skillsRoot 'codex-permission-tools'
$legacySkillNamespace = Join-Path $skillsRoot 'codex-fewer-permission-prompts'
$skillTarget = Join-Path $repoRoot 'skills'

if (-not (Test-Path $repoRoot)) {
    throw 'codex-fewer-permission-prompts is not installed. Follow INSTALL.md first.'
}

git -C $repoRoot pull --ff-only
python -m pip install --user -e $repoRoot

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null

if (Test-Path $legacySkillNamespace) {
    $legacyItem = Get-Item -LiteralPath $legacySkillNamespace -Force
    $legacyTarget = @($legacyItem.Target)[0]
    $legacyTargetMatches = $false
    if ($legacyItem.LinkType -eq 'Junction' -and $legacyTarget) {
        $legacyTargetMatches = [System.IO.Path]::GetFullPath($legacyTarget).TrimEnd('\') -ieq [System.IO.Path]::GetFullPath($skillTarget).TrimEnd('\')
    }
    if (-not $legacyTargetMatches) {
        throw "Legacy skill namespace exists but does not point to this install: $legacySkillNamespace"
    }
    if (-not (Test-Path $skillNamespace)) {
        cmd /d /c "mklink /J `"$skillNamespace`" `"$skillTarget`""
    }
    cmd /d /c "rmdir `"$legacySkillNamespace`""
}

if (-not (Test-Path $skillNamespace)) {
    cmd /d /c "mklink /J `"$skillNamespace`" `"$skillTarget`""
}

python -m codex_fewer_permission_prompts doctor --json
```

Report the JSON result in the reply. Because update may change skill files, explicitly tell the user:

```text
请重启 Codex App 并回到这个对话，或新开 CLI 实例，让它重新扫描 ~/.agents/skills；然后再说“/fewer-permission-prompts doctor”。
```
