#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$scratchRoot = Join-Path $repoRoot '_sandbox'
$testRoot = Join-Path $scratchRoot ('initialize-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $testRoot 'scripts') -Force | Out-Null

function Assert-InitializeCheck {
    param($Condition, [string]$Message)

    if (-not $Condition) {
        throw $Message
    }
}

function Expect-InitializeFailure {
    param([scriptblock]$Action)

    try {
        & $Action | Out-Null
    } catch {
        return $_.Exception.Message
    }

    throw 'Expected initialization to fail.'
}

try {
    # Run copies so the real machine configuration and developer assets are never touched.
    Copy-Item -LiteralPath (Join-Path $repoRoot 'initialize.ps1') -Destination $testRoot
    Copy-Item -LiteralPath (Join-Path $repoRoot 'scripts/project-config.ps1') -Destination (Join-Path $testRoot 'scripts')

    $fakeBlender = Join-Path $testRoot 'fake-blender.ps1'
    @'
Write-Output 'Blender initialization test fixture'
$global:LASTEXITCODE = 0
'@ | Set-Content -LiteralPath $fakeBlender

    # This stand-in checks the call order without downloading anything.
    @'
$configPath = Join-Path $PSScriptRoot '../.immersive-suicide.local.json'
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($config.schema -ne 1 -or -not $config.blender_path) {
    throw 'Restoration started before configuration was saved.'
}
Add-Content -LiteralPath (Join-Path $PSScriptRoot '../restore-calls.txt') -Value 'called'
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '../fail-restore')) {
    throw 'Simulated download failure.'
}
'@ | Set-Content -LiteralPath (Join-Path $testRoot 'scripts/restore-developer-assets.ps1')

    $initializer = Join-Path $testRoot 'initialize.ps1'
    $configPath = Join-Path $testRoot '.immersive-suicide.local.json'
    $callsPath = Join-Path $testRoot 'restore-calls.txt'

    # Fresh setup restores assets once, after writing the configuration.
    Push-Location $testRoot
    try {
        & $initializer -BlenderPath $fakeBlender
    } finally {
        Pop-Location
    }
    $configText = [IO.File]::ReadAllText($configPath)
    Assert-InitializeCheck (@(Get-Content -LiteralPath $callsPath).Count -eq 1) 'Fresh setup did not restore assets once.'

    # Existing configuration must still require -Force before anything changes.
    $errorText = Expect-InitializeFailure { & $initializer -BlenderPath $fakeBlender }
    Assert-InitializeCheck ($errorText.Contains('already exists')) 'Existing configuration guard changed.'
    Assert-InitializeCheck ([IO.File]::ReadAllText($configPath) -ceq $configText) 'Configuration was overwritten without -Force.'
    Assert-InitializeCheck (@(Get-Content -LiteralPath $callsPath).Count -eq 1) 'Rejected setup still restored assets.'

    # Configuration-only setup should not call the restorer.
    Remove-Item -LiteralPath $configPath
    & $initializer -BlenderPath $fakeBlender -SkipAssetRestore
    Assert-InitializeCheck (Test-Path -LiteralPath $configPath) 'Configuration-only setup did not save configuration.'
    Assert-InitializeCheck (@(Get-Content -LiteralPath $callsPath).Count -eq 1) '-SkipAssetRestore still restored assets.'

    # An explicit rerun with -Force restores unless the skip switch is supplied.
    & $initializer -BlenderPath $fakeBlender -Force
    Assert-InitializeCheck (@(Get-Content -LiteralPath $callsPath).Count -eq 2) '-Force setup did not restore assets.'

    # A download error must propagate while leaving usable configuration for retry.
    [IO.File]::WriteAllText((Join-Path $testRoot 'fail-restore'), 'fail')
    $errorText = Expect-InitializeFailure { & $initializer -BlenderPath $fakeBlender -Force }
    Assert-InitializeCheck ($errorText.Contains('Simulated download failure')) 'Restore error was swallowed.'
    $savedConfig = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    Assert-InitializeCheck ($savedConfig.blender_path -eq $fakeBlender) 'Restore failure removed the saved configuration.'

    Write-Host 'INITIALIZE_TESTS_PASSED'
} finally {
    $resolved = [IO.Path]::GetFullPath($testRoot)
    $allowed = [IO.Path]::GetFullPath($scratchRoot) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($allowed) -or (Split-Path -Leaf $resolved) -notlike 'initialize-test-*') {
        throw 'Unsafe initialization test cleanup target.'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
