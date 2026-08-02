$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." -Resolve)).Path
$targets = @(
    (Join-Path $projectRoot "build"),
    (Join-Path $projectRoot "dist\data")
)

foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) {
        $resolvedTarget = (Resolve-Path -LiteralPath $target).Path
        $resolvedProject = (Resolve-Path -LiteralPath $projectRoot).Path
        if (-not $resolvedTarget.StartsWith($resolvedProject + [IO.Path]::DirectorySeparatorChar)) {
            throw "Refusing to delete a path outside the project: $resolvedTarget"
        }
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
        Write-Output "Removed: $resolvedTarget"
    }
}
