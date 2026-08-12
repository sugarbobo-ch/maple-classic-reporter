$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." -Resolve)).Path
$buildRoot = Join-Path $projectRoot "build"
$distRoot = Join-Path $projectRoot "dist"
$bundleRoot = Join-Path $distRoot "MapleClassicReporter"
$oauthConfig = Join-Path $projectRoot "build_secrets\google_oauth_client.json"

if (-not (Test-Path -LiteralPath $oauthConfig -PathType Leaf)) {
    throw "Release build requires build_secrets\google_oauth_client.json. The file is intentionally excluded from Git."
}

if (Test-Path -LiteralPath $buildRoot) {
    Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
}
$legacyTargetExe = Join-Path $distRoot "MapleClassicReporter.exe"
if (Test-Path -LiteralPath $legacyTargetExe) {
    Remove-Item -LiteralPath $legacyTargetExe -Force -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $bundleRoot) {
    Remove-Item -LiteralPath $bundleRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Push-Location $projectRoot
try {
    & uv sync --frozen
    if ($LASTEXITCODE -ne 0) {
        throw "Locked dependency sync failed with exit code $LASTEXITCODE."
    }

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

$targetExe = Join-Path $bundleRoot "MapleClassicReporter.exe"
if (-not (Test-Path -LiteralPath $targetExe -PathType Leaf)) {
    throw "PyInstaller completed but the onedir executable was not found: $targetExe"
}

Write-Output "Built: $targetExe"
Write-Output "Distribution folder: $bundleRoot"
