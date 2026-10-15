param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $PSScriptRoot
$releasePython = Join-Path $releaseRoot '.venv-publish\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $releasePython)) {
    throw 'The prepared publishing environment is missing.'
}
$releaseConfig = Join-Path $releaseRoot 'pyproject.toml'
$releaseVersion = & $releasePython -c 'import pathlib,sys,tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["version"])' $releaseConfig
if ($LASTEXITCODE -ne 0 -or -not $releaseVersion) { throw 'Cannot read project version.' }
$releaseDir = Join-Path $releaseRoot ('.pypi-dist\' + $releaseVersion)
$wheel = Join-Path $releaseDir ("pydara-$releaseVersion-py3-none-any.whl")
$source = Join-Path $releaseDir ("pydara-$releaseVersion.tar.gz")
$hashFile = Join-Path $releaseDir 'SHA256SUMS.json'
$hashes = Get-Content -LiteralPath $hashFile -Raw | ConvertFrom-Json
foreach ($artifact in @($wheel, $source)) {
    $filename = Split-Path -Leaf $artifact
    $expected = $hashes.$filename
    if (-not $expected -or (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw "Release checksum mismatch: $filename"
    }
}
& $releasePython -m twine check --strict $wheel $source
if ($LASTEXITCODE -ne 0) { throw 'Package validation failed.' }
if ($CheckOnly) { exit 0 }
Write-Host "Publishing pydara $releaseVersion to the production PyPI registry."
Write-Host 'Paste your PyPI API token at the hidden password prompt. It is not saved by this script.'
& $releasePython -m twine upload --repository-url https://upload.pypi.org/legacy/ --username __token__ --disable-progress-bar $wheel $source
if ($LASTEXITCODE -ne 0) { throw 'Upload failed. Review the PyPI response before retrying.' }
Write-Host "Published: https://pypi.org/project/pydara/$releaseVersion/"
