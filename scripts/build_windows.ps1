$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." -Resolve)).Path
$buildRoot = Join-Path $projectRoot "build"
$distRoot = Join-Path $projectRoot "dist"

foreach ($target in @($buildRoot, $distRoot)) {
    if (Test-Path -LiteralPath $target) {
        $resolvedTarget = (Resolve-Path -LiteralPath $target).Path
        $resolvedProject = (Resolve-Path -LiteralPath $projectRoot).Path
        if (-not $resolvedTarget.StartsWith($resolvedProject + [IO.Path]::DirectorySeparatorChar)) {
            throw "Refusing to delete a path outside the project: $resolvedTarget"
        }
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
    }
}

Push-Location $projectRoot
try {
    & uv run playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        throw "Playwright Chromium installation failed with exit code $LASTEXITCODE."
    }

    & uv run pyinstaller --noconfirm --clean MapleClassicReporter.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}

Write-Output "Built: $(Join-Path $distRoot 'MapleClassicReporter.exe')"
