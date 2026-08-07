$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." -Resolve)).Path
$buildRoot = Join-Path $projectRoot "build"
$distRoot = Join-Path $projectRoot "dist"

if (Test-Path -LiteralPath $buildRoot) {
    Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
}
$targetExe = Join-Path $distRoot "MapleClassicReporter.exe"
if (Test-Path -LiteralPath $targetExe) {
    Remove-Item -LiteralPath $targetExe -Force -ErrorAction SilentlyContinue
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
