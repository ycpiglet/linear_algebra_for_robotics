[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $TaskArguments
)

$ErrorActionPreference = 'Stop'
$TaskArguments = @($TaskArguments)
if ($TaskArguments.Count -eq 0) {
    $TaskArguments = @('bootstrap')
}
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root 'scripts\dev.py'
$manifest = Join-Path $root 'scripts\toolchain.json'
$expectedRunnerSha256 = 'c92c57aa987418fa735daccbd49fca5953af84feafe25fdab433fbb36daf8c00'
$expectedManifestSha256 = 'c01f9870c97867b7bb65a903205252c509e19a191b6b9a11250ac59206356316'

$actualRunnerSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLowerInvariant()
$actualManifestSha256 = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $manifest
).Hash.ToLowerInvariant()
if ($actualRunnerSha256 -cne $expectedRunnerSha256) {
    throw "scripts\dev.py does not match this reviewed wrapper."
}
if ($actualManifestSha256 -cne $expectedManifestSha256) {
    throw "scripts\toolchain.json does not match this reviewed wrapper."
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $py) {
    & $py.Source -3 $runner @TaskArguments
    exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -ne $python) {
    & $python.Source $runner @TaskArguments
    exit $LASTEXITCODE
}

throw 'Python 3 is required. Install it with: winget install Python.Python.3.12'
