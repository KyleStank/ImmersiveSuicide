# These tests use temporary files. They do not change the real configuration or start Blender/the game.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../scripts/project-config.ps1"

function Expect-ConfigFailure {
    param(
        [scriptblock]$Action
    )

    $failed = $false

    try {
        & $Action | Out-Null
    } catch {
        $failed = $true
    }

    if (-not $failed) {
        throw 'Expected invalid configuration to fail.'
    }
}

# Give this test run its own temporary folder.
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('pz-config-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null

try {
    $testConfig = Join-Path $testRoot 'local.json'
    $testExecutable = Join-Path $testRoot 'executable with spaces'
    [IO.File]::WriteAllText($testExecutable, 'not executed')

    $testGame = Join-Path $testRoot 'game with spaces'
    New-Item -ItemType Directory -Path (Join-Path $testGame 'media') | Out-Null

    # A missing configuration should fail.
    Expect-ConfigFailure {
        Get-ProjectLocalConfig -Path $testConfig
    }

    # Blender alone is enough for a valid configuration.
    $data = @{
        schema = 1
        blender_path = $testExecutable
        project_zomboid_path = $null
    }

    $data | ConvertTo-Json | Set-Content -LiteralPath $testConfig -Encoding utf8

    if ((Get-ProjectLocalConfig -Path $testConfig).blender_path -ne $testExecutable) {
        throw 'Blender-only config failed'
    }

    # Adding a valid game path should also work.
    $data.project_zomboid_path = $testGame
    $data | ConvertTo-Json | Set-Content -LiteralPath $testConfig -Encoding utf8
    Get-ProjectLocalConfig -Path $testConfig | Out-Null

    # Reject relative paths, missing files and folders used as executables.
    foreach ($badPath in @('relative', (Join-Path $testRoot 'missing'), $testGame)) {
        $data.blender_path = $badPath
        $data | ConvertTo-Json | Set-Content -LiteralPath $testConfig -Encoding utf8

        Expect-ConfigFailure {
            Get-ProjectLocalConfig -Path $testConfig
        }
    }

    # A game folder without media/ should fail.
    $data.blender_path = $testExecutable
    $data.project_zomboid_path = $testRoot
    $data | ConvertTo-Json | Set-Content -LiteralPath $testConfig -Encoding utf8

    Expect-ConfigFailure {
        Get-ProjectLocalConfig -Path $testConfig
    }

    # Reject unsupported schema versions and values that are not integers.
    $data.project_zomboid_path = $null
    $data.schema = 99
    $data | ConvertTo-Json | Set-Content -LiteralPath $testConfig -Encoding utf8

    Expect-ConfigFailure {
        Get-ProjectLocalConfig -Path $testConfig
    }

    foreach ($badSchema in @('1', $true, $null)) {
        $data.schema = $badSchema
        $data | ConvertTo-Json | Set-Content -LiteralPath $testConfig -Encoding utf8

        Expect-ConfigFailure {
            Get-ProjectLocalConfig -Path $testConfig
        }
    }

    # Reject unknown fields and invalid JSON.
    $data.schema = 1
    $data['unknown'] = 'rejected'
    $data | ConvertTo-Json | Set-Content -LiteralPath $testConfig -Encoding utf8

    Expect-ConfigFailure {
        Get-ProjectLocalConfig -Path $testConfig
    }

    [IO.File]::WriteAllText($testConfig, 'not json')

    Expect-ConfigFailure {
        Get-ProjectLocalConfig -Path $testConfig
    }

    # A supplied Blender path should work without reading the configuration.
    if ((Resolve-ProjectBlender $testExecutable) -ne $testExecutable) {
        throw 'Explicit override failed'
    }

    Write-Host 'LOCAL_CONFIG_TESTS_PASSED'
} finally {
    # Check the folder before deleting it. Only remove this test run's temporary files.
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $resolved = [IO.Path]::GetFullPath($testRoot)

    if (-not $resolved.StartsWith($tempRoot) -or (Split-Path -Leaf $resolved) -notlike 'pz-config-test-*') {
        throw 'Unsafe config test cleanup'
    }

    Remove-Item -LiteralPath $resolved -Recurse
}
