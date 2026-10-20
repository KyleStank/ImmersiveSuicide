[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [string]$Spec,

    [ValidateSet('template', 'retime', 'export')]
    [string]$Operation = 'template',

    [string]$Name,
    [string]$BlenderPath,
    [string]$GripReference,
    [switch]$Stage
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../../../../scripts/project-config.ps1"

$BlenderPath = Resolve-ProjectBlender $BlenderPath
$skillRoot = Split-Path -Parent $PSScriptRoot
$repo = [IO.Path]::GetFullPath((Join-Path $skillRoot '../../..'))

# Find inputs relative to the skill, repository or supplied absolute path.
function Resolve-Input([string]$value) {
    if ($value.StartsWith('skill:')) {
        return (Resolve-Path -LiteralPath (Join-Path $skillRoot $value.Substring(6))).Path
    }

    if ($value.StartsWith('repo:')) {
        return (Resolve-Path -LiteralPath (Join-Path $repo $value.Substring(5))).Path
    }

    if ([IO.Path]::IsPathRooted($value)) {
        return (Resolve-Path -LiteralPath $value).Path
    }

    if (Test-Path -LiteralPath (Join-Path $repo $value)) {
        return (Resolve-Path -LiteralPath (Join-Path $repo $value)).Path
    }

    return (Resolve-Path -LiteralPath (Join-Path $skillRoot $value)).Path
}

# Read the recipe and check output paths before starting Blender.
$specPath = Resolve-Input $Spec
$data = Get-Content -LiteralPath $specPath -Raw | ConvertFrom-Json

$clip = if ($Name) {
    $Name
} else {
    [string]$data.name
}

if ($clip -cnotmatch '^Bob_[A-Za-z0-9_]+$') {
    throw 'Invalid animation name'
}

if (-not (Test-Path -LiteralPath $BlenderPath -PathType Leaf)) {
    throw "Blender not found: $BlenderPath"
}

$output = Join-Path $skillRoot "work/output/$clip"

if (Test-Path -LiteralPath $output) {
    throw "Protected output exists: $output. Use a new name."
}

$destination = Join-Path $repo "Contents/mods/ImmersiveSuicide/42.0/media/anims_X/Bob/$clip.glb"

if ($Stage -and (Test-Path -LiteralPath $destination)) {
    throw 'Staged clip exists; choose a new name.'
}

# Save hashes so we can check that the original inputs were not changed.
$template = Join-Path $skillRoot 'assets/rig/PZ_HumanRigV4.blend'
$protected = @{}

foreach ($inputPath in @($template, $specPath)) {
    $protected[$inputPath] = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash
}

if ($data.source_blend) {
    $sourceValue = [string]$data.source_blend
    $source = if ([IO.Path]::IsPathRooted($sourceValue) -or $sourceValue.StartsWith('skill:') -or $sourceValue.StartsWith('repo:')) {
        Resolve-Input $sourceValue
    } else {
        (Resolve-Path -LiteralPath (Join-Path (Split-Path -Parent $specPath) $sourceValue)).Path
    }

    $protected[$source] = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
}

if ($GripReference) {
    $grip = Resolve-Input $GripReference
    $protected[$grip] = (Get-FileHash -LiteralPath $grip -Algorithm SHA256).Hash
}

function Assert-ProtectedInputs {
    foreach ($inputPath in $protected.Keys) {
        if ((Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash -ne $protected[$inputPath]) {
            throw "Protected source changed during operation: $inputPath"
        }
    }
}

Push-Location $repo

try {
    $blend = Join-Path $output "$clip.blend"
    $glb = Join-Path $output "$clip.glb"

    # Work on a copy, or export/retime the source selected by the recipe.
    if ($Operation -eq 'template') {
        New-Item -ItemType Directory -Path $output | Out-Null
        [IO.File]::Copy($template, $blend, $false)

        & $BlenderPath --background $blend --python-exit-code 1 --python "$PSScriptRoot/blender/build_animation.py" -- --spec $specPath --output-dir $output --name $clip
    } else {
        $arguments = @(
            '--background', '--python-exit-code', '1', '--python',
            "$PSScriptRoot/blender/retime_clip.py", '--', $specPath, '--name', $clip
        )

        if ($Operation -eq 'export') {
            $arguments += '--export-only'
        }

        & $BlenderPath @arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Blender $Operation failed; no clip staged."
    }

    # Check the GLB and compare its joint positions with the working blend.
    $report = Get-Content -LiteralPath (Join-Path $output 'validation.json') -Raw | ConvertFrom-Json

    if (-not $report.valid) {
        throw 'Invalid GLB report'
    }

    $checkOutput = & $BlenderPath --background --python-exit-code 1 --python "$PSScriptRoot/blender/verify_export_positions.py" -- $blend $glb 2>&1
    $checkExit = $LASTEXITCODE
    $checkOutput | ForEach-Object { Write-Host $_ }

    if ($checkExit -ne 0) {
        throw 'Export round-trip failed; no clip staged.'
    }

    $checkLine = $checkOutput | Where-Object { "$_" -like 'EXPORT_POSITION_CHECK *' } | Select-Object -Last 1

    if (-not $checkLine) {
        throw 'Missing export verification result'
    }

    $positionCheck = ("$checkLine" -replace '^EXPORT_POSITION_CHECK ', '') | ConvertFrom-Json

    if ($GripReference) {
        & $BlenderPath --background --python-exit-code 1 --python "$PSScriptRoot/blender/verify_grip_reference.py" -- $grip $blend

        if ($LASTEXITCODE -ne 0) {
            throw 'Grip verification failed; no clip staged.'
        }
    }

    Assert-ProtectedInputs

    # Record which inputs and checks produced these files.
    @{
        operation = $Operation
        clip = $clip
        recipe = $specPath
        protected_inputs = $protected
        blend_sha256 = (Get-FileHash -LiteralPath $blend -Algorithm SHA256).Hash
        glb_sha256 = (Get-FileHash -LiteralPath $glb -Algorithm SHA256).Hash
        export_position_check = $positionCheck
        grip_verified = [bool]$GripReference
        in_game_verified = $false
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'build-record.json') -Encoding utf8

    # Staging only copies the GLB into the workspace mod folder.
    if ($Stage) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        [IO.File]::Copy($glb, $destination, $false)
        Write-Host "Staged in workspace only: $destination"
    }

    Write-Host "Ready for visual review: $blend"
} finally {
    try {
        Assert-ProtectedInputs
    } finally {
        Pop-Location
    }
}
