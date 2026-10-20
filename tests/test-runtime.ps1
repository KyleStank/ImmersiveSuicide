# Requires a JDK that can run Java source files and a configured Build 42 installation.
[CmdletBinding()]
param(
    [string]$JavaPath = "java"
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../scripts/project-config.ps1"

# Read the game path so the tests can use its Lua compiler and base classes.
$runtimeGame = (Get-ProjectLocalConfig).project_zomboid_path

if (-not $runtimeGame) {
    throw 'Initialize with -ProjectZomboidPath first.'
}

$runtimeRoot = Split-Path $PSScriptRoot -Parent

# Run the tests without starting the game or loading a save.
& $JavaPath -cp (Join-Path $runtimeGame 'projectzomboid.jar') "$PSScriptRoot/runtime/RunRuntimeTests.java" $runtimeGame $runtimeRoot

if ($LASTEXITCODE -ne 0) {
    throw 'Runtime behavioral checks failed.'
}
