# Copies the validator out of the UE project into this repo folder (one source of truth: the project).
# Usage: powershell -ExecutionPolicy Bypass -File sync_repo.ps1
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$proj = Resolve-Path (Join-Path $repo "..\..")

$items = @(
    @{ From = "Content\Python\asset_validator";  To = "Content\Python\asset_validator" },
    @{ From = "Config\AssetValidator";           To = "Config\AssetValidator" },
    @{ From = "Content\Tools\AssetValidator";    To = "Content\Tools\AssetValidator" }
)
foreach ($i in $items) {
    $src = Join-Path $proj $i.From
    $dst = Join-Path $repo $i.To
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    Copy-Item $src $dst -Recurse
}
Get-ChildItem $repo -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Write-Host "Synced into $repo"
