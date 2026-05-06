# codex-fewer-permission-prompts uninstall for Codex

Use these instructions when an engineer asks Codex to uninstall the Codex fewer permission prompts skill.

## One-paste prompt for engineers

```text
Fetch and follow instructions from https://raw.githubusercontent.com/gaoguobin/codex-fewer-permission-prompts/main/.codex/UNINSTALL.md
```

## Uninstall steps

Uninstall removes only this tool's skill, package, repo, and sentinel block from the default rules file. It preserves unrelated Codex rules and unrelated skill entries.

If the user explicitly wants to keep the applied permission rules, skip the `rollback --remove-block` line. Otherwise keep it: the command backs up the rules file first and removes only the `codex-fewer-permission-prompts` sentinel block.

If the Codex environment uses sandbox or approval controls, request approval/escalation for uninstall because it may edit `%USERPROFILE%\.codex\rules\default.rules`, uninstall a Python package, remove a junction under `%USERPROFILE%\.agents`, and delete `%USERPROFILE%\.codex\codex-fewer-permission-prompts` and `%USERPROFILE%\.codex\codex-fewer-permission-prompts-skill`.

If any command fails because of permissions, sandbox write limits, process locks, or junction removal, do not try unrelated workarounds. Ask for approval and rerun the same intended uninstall step.

Run this PowerShell block exactly:

```powershell
$repoRoot = Join-Path $HOME '.codex\codex-fewer-permission-prompts'
$skillMirrorRoot = Join-Path $HOME '.codex\codex-fewer-permission-prompts-skill'
$skillMirror = Join-Path $skillMirrorRoot 'codex-fewer-permission-prompts'
$skillLink = Join-Path $HOME '.agents\skills\codex-fewer-permission-prompts'
$legacyNamespace = Join-Path $HOME '.agents\skills\codex-permission-tools'
$legacyParentTarget = Join-Path $repoRoot 'skills'
$legacyInnerTarget = Join-Path $repoRoot 'skills\codex-fewer-permission-prompts'
$rulesFile = Join-Path $HOME '.codex\rules\default.rules'

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
    throw "Refusing to remove unexpected skill junction: $path"
}

if (Test-Path $repoRoot) {
    $env:PYTHONPATH = Join-Path $repoRoot 'src'
    if (Test-Path $rulesFile) {
        python -m codex_fewer_permission_prompts rollback --rules-file $rulesFile --remove-block --yes
    }
}

python -m pip uninstall -y codex-fewer-permission-prompts

Remove-ExpectedJunction $skillLink @($legacyParentTarget, $legacyInnerTarget, $skillMirror)
Remove-ExpectedJunction $legacyNamespace @($legacyParentTarget, $legacyInnerTarget, $skillMirror)

if (Test-Path $skillMirrorRoot) {
    Remove-Item -LiteralPath $skillMirrorRoot -Recurse -Force
}

if (Test-Path $repoRoot) {
    Remove-Item -LiteralPath $repoRoot -Recurse -Force
}
```

When cleanup completes, explicitly tell the user:

```text
请重启 Codex App，或新开 CLI 实例，让它从 skill 列表中移除 codex-fewer-permission-prompts，并让 rules 重新加载。
```
