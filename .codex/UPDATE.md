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
$skillLink = Join-Path $skillsRoot 'codex-fewer-permission-prompts'
$legacyNamespace = Join-Path $skillsRoot 'codex-permission-tools'
$legacyParentTarget = Join-Path $repoRoot 'skills'
$skillTarget = Join-Path $repoRoot 'skills\codex-fewer-permission-prompts'

function Test-JunctionTarget($path, $target) {
    if (-not (Test-Path $path)) {
        return $false
    }
    $item = Get-Item -LiteralPath $path -Force
    $currentTarget = @($item.Target)[0]
    if ($item.LinkType -ne 'Junction' -or -not $currentTarget) {
        return $false
    }
    return [System.IO.Path]::GetFullPath($currentTarget).TrimEnd('\') -ieq [System.IO.Path]::GetFullPath($target).TrimEnd('\')
}

function Remove-ExpectedJunction($path, $targets) {
    if (-not (Test-Path $path)) {
        return
    }
    foreach ($target in $targets) {
        if (Test-JunctionTarget $path $target) {
            cmd /d /c "rmdir `"$path`""
            return
        }
    }
    throw "Skill path exists but does not point to this install: $path"
}

if (-not (Test-Path $repoRoot)) {
    throw 'codex-fewer-permission-prompts is not installed. Follow INSTALL.md first.'
}

git -C $repoRoot pull --ff-only
python -m pip install --user -e $repoRoot

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null

Remove-ExpectedJunction $legacyNamespace @($legacyParentTarget, $skillTarget)

if (Test-Path $skillLink) {
    if (Test-JunctionTarget $skillLink $legacyParentTarget) {
        cmd /d /c "rmdir `"$skillLink`""
    } elseif (-not (Test-JunctionTarget $skillLink $skillTarget)) {
        throw "Skill path exists but does not point to this install: $skillLink"
    }
}

if (-not (Test-Path $skillLink)) {
    cmd /d /c "mklink /J `"$skillLink`" `"$skillTarget`""
}

python -m codex_fewer_permission_prompts doctor --json
```

Report the JSON result in the reply. Because update may change skill files, explicitly tell the user:

```text
请完全重启 Codex App 后新开一个对话，或新开 CLI 实例，让它重新扫描 ~/.agents/skills；然后再说“/fewer-permission-prompts doctor”。不要用更新时的旧对话判断 / 菜单是否已刷新，因为旧 thread 可能缓存更新前的 skill 列表。
```
