[CmdletBinding()]
param(
    [string]$BlenderPath
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../../../../scripts/project-config.ps1"

$BlenderPath = Resolve-ProjectBlender $BlenderPath
& "$PSScriptRoot/../../../../tests/test-project-config.ps1"

$skill = Split-Path -Parent $PSScriptRoot
$repo = [IO.Path]::GetFullPath((Join-Path $skill '../../..'))
$tool = Join-Path $skill 'scripts/animation-toolkit.ps1'

# Use new names so the tests cannot overwrite previous outputs.
$id = [guid]::NewGuid().ToString('N').Substring(0, 10)
$names = @(
    "Bob_IS_Verify_${id}_Template",
    "Bob_IS_Verify_${id}_Retime",
    "Bob_IS_Verify_${id}_Export",
    "Bob_IS_Verify_${id}_Invalid",
    "Bob_IS_Verify_${id}_HeadExport"
)

$work = Join-Path $skill 'work'
$invalid = Join-Path $work "invalid-$id.json"
$passed = $false

Push-Location $repo

try {
    # Check paths, source hashes and curve handling first.
    & $BlenderPath --background --python-exit-code 1 --python "$PSScriptRoot/test-animation-toolkit.py"

    if ($LASTEXITCODE -ne 0) {
        throw 'Contract tests failed'
    }

    & $BlenderPath --background --python-exit-code 1 --python "$PSScriptRoot/test_retime_animation.py"

    if ($LASTEXITCODE -ne 0) {
        throw 'Curve tests failed'
    }

    # Exercise all three toolkit operations using the test recipes.
    & $tool assets/specs/hand-gesture.json -Name $names[0] -BlenderPath $BlenderPath
    & $tool assets/specs/retime.json -Operation retime -Name $names[1] -BlenderPath $BlenderPath
    & $tool assets/specs/export-final.json -Operation export -Name $names[2] -BlenderPath $BlenderPath -GripReference skill:assets/examples/short-blade-one-hand/03-approved-finger-grip.blend

    # The exported motion should match the approved reference GLB.
    $gold = Join-Path $skill 'assets/examples/short-blade-one-hand/07-approved-overlapping-collapse.glb'
    $export = Join-Path $skill "work/output/$($names[2])/$($names[2]).glb"

    & $BlenderPath --background --python-exit-code 1 --python "$skill/scripts/blender/compare_clip_motion.py" -- $gold $export

    if ($LASTEXITCODE -ne 0) {
        throw 'Golden export changed'
    }

    # Compare the second example's exported motion without imposing the first grip's key layout.
    & $tool assets/specs/export-head-stab.json -Operation export -Name $names[4] -BlenderPath $BlenderPath
    $headReference = Join-Path $skill 'assets/examples/head-stab/04-reviewed-backward-fall.glb'
    $headExport = Join-Path $skill "work/output/$($names[4])/$($names[4]).glb"
    & $BlenderPath --background --python-exit-code 1 --python "$skill/scripts/blender/compare_clip_motion.py" -- $headReference $headExport

    if ($LASTEXITCODE -ne 0) {
        throw 'Head-stab reference export changed'
    }

    # Reusing an output name should fail without changing the existing file.
    $before = (Get-FileHash -LiteralPath $export).Hash

    try {
        & $tool assets/specs/export-final.json -Operation export -Name $names[2] -BlenderPath $BlenderPath
        throw 'Overwrite was unexpectedly allowed'
    } catch {
        if ($_.Exception.Message -notlike 'Protected output exists:*') {
            throw
        }
    }

    if ((Get-FileHash -LiteralPath $export).Hash -ne $before) {
        throw 'Overwrite guard changed a result'
    }

    # An invalid recipe should fail before anything is staged.
    $bad = Get-Content -LiteralPath (Join-Path $skill 'assets/specs/hand-gesture.json') -Raw | ConvertFrom-Json
    $bad.tracks[0].keyframes[1].frame = 1.5
    $bad | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $invalid -Encoding utf8

    try {
        & $tool $invalid -Name $names[3] -BlenderPath $BlenderPath -Stage
        throw 'Invalid recipe was unexpectedly accepted'
    } catch {
        if ($_.Exception.Message -notlike 'Blender template failed*') {
            throw
        }
    }

    $staged = Join-Path $repo "Contents/mods/ImmersiveSuicide/42.0/media/anims_X/Bob/$($names[3]).glb"

    if (Test-Path -LiteralPath $staged) {
        throw 'Failed build was staged'
    }

    # Check the original sources again after the test builds.
    & $BlenderPath --background --python-exit-code 1 --python "$PSScriptRoot/test-animation-toolkit.py"

    if ($LASTEXITCODE -ne 0) {
        throw 'Post-build source integrity failed'
    }

    @{
        passed = $true
        contract_tests = 18
        operations = @('template', 'retime', 'export')
        fixed_grip = $true
        golden_export = $true
        head_stab_reference_export = $true
        overwrite_refused = $true
        failed_build_not_staged = $true
        blender = $BlenderPath
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'test-results.json') -Encoding utf8

    $passed = $true
    Write-Host 'TOOLKIT_VERIFICATION_PASSED'
} finally {
    # Only delete files created by this test run. Keep failed outputs for inspection.
    if ($passed) {
        $outputRoot = [IO.Path]::GetFullPath((Join-Path $work 'output'))

        foreach ($name in $names) {
            $target = [IO.Path]::GetFullPath((Join-Path $outputRoot $name))

            if (-not $target.StartsWith($outputRoot + [IO.Path]::DirectorySeparatorChar) -or $name -notlike "Bob_IS_Verify_${id}_*") {
                throw 'Unsafe test cleanup target'
            }

            if (Test-Path -LiteralPath $target) {
                Remove-Item -LiteralPath $target -Recurse
            }
        }

        if (Test-Path -LiteralPath $invalid) {
            Remove-Item -LiteralPath $invalid
        }
    }

    Pop-Location
}
