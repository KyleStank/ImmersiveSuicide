[CmdletBinding()]
param(
    [string]$BlenderPath,
    [string]$ProjectZomboidPath,
    [switch]$Force,
    [switch]$SkipAssetRestore
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/scripts/project-config.ps1"

# Only replace an existing configuration when -Force is supplied.
if ((Test-Path -LiteralPath $ProjectConfigPath) -and -not $Force) {
    throw 'Local project configuration already exists. Use -Force to deliberately replace it.'
}

# Find Blender on PATH, or ask for its location.
if (-not $BlenderPath) {
    $command = Get-Command blender -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1

    $BlenderPath = if ($command) {
        $command.Source
    } else {
        Read-Host 'Absolute path to the Blender executable'
    }
}

Assert-ProjectLocalPath $BlenderPath Leaf 'blender_path'

# The game path is optional. If supplied, check that it contains media/.
$game = $null

if ($ProjectZomboidPath) {
    Assert-ProjectLocalPath $ProjectZomboidPath Container 'project_zomboid_path'

    if (-not (Test-Path -LiteralPath (Join-Path $ProjectZomboidPath 'media') -PathType Container)) {
        throw 'Supply the Project Zomboid installation containing media/, not the user save/mods directory.'
    }

    $game = (Resolve-Path -LiteralPath $ProjectZomboidPath).Path
}

# Make sure the executable is actually Blender before saving anything.
$version = & $BlenderPath --version

if ($LASTEXITCODE -ne 0 -or "$($version | Select-Object -First 1)" -notmatch '^Blender ') {
    throw 'The selected executable did not identify itself as Blender. Configuration was not written.'
}

$data = @{
    schema = 1
    blender_path = (Resolve-Path -LiteralPath $BlenderPath).Path
    project_zomboid_path = $game
}

# Without -Force, also refuse to overwrite a file created since the first check.
$mode = if ($Force) {
    [IO.FileMode]::Create
} else {
    [IO.FileMode]::CreateNew
}

$stream = [IO.File]::Open($ProjectConfigPath, $mode, [IO.FileAccess]::Write, [IO.FileShare]::None)

try {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($data | ConvertTo-Json) + "`n")
    $stream.Write($bytes, 0, $bytes.Length)
} finally {
    $stream.Dispose()
}

Write-Host ($version | Select-Object -First 1)
Write-Host "Local configuration saved: $ProjectConfigPath"

if (-not $game) {
    Write-Host 'Game path omitted: exports work; game: previews/diagnostics require reinitialization with -ProjectZomboidPath and -Force.'
}

# Save the configuration first so a failed download can be retried separately.
if (-not $SkipAssetRestore) {
    & "$PSScriptRoot/scripts/restore-developer-assets.ps1"
}

Write-Host 'Project initialization complete.'
