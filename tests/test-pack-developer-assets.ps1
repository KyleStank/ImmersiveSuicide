#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$packer = Join-Path $repoRoot 'scripts/pack-developer-assets.ps1'
$scratchRoot = Join-Path $repoRoot '_sandbox'
$testRoot = Join-Path $scratchRoot ('pack-assets-test-' + [guid]::NewGuid().ToString('N'))

function Assert-PackCheck {
    param($Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Expect-PackFailure {
    param([scriptblock]$Action)
    $failed = $false
    try {
        & $Action | Out-Null
    } catch {
        $failed = $true
    }
    Assert-PackCheck $failed 'Expected packing to fail.'
}

New-Item -ItemType Directory -Path (Join-Path $testRoot '.hidden') -Force | Out-Null

try {
    # Use small stand-in files so the real developer assets stay untouched.
    $firstSource = Join-Path $testRoot 'one.blend'
    $secondSource = Join-Path $testRoot '.hidden/two.blend'
    [IO.File]::WriteAllText($firstSource, 'first test asset')
    [IO.File]::WriteAllText($secondSource, 'second test asset')
    [IO.File]::WriteAllText("${firstSource}1", 'unlisted backup')

    $files = @(
        foreach ($source in @($firstSource, $secondSource)) {
            @{
                path = [IO.Path]::GetRelativePath($repoRoot, $source).Replace('\', '/')
                sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }
    )

    $manifestPath = Join-Path $testRoot 'manifest.json'
    $manifestText = @{ schema = 1; files = $files } | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($manifestPath, $manifestText)
    $outputPath = Join-Path $testRoot 'output/assets.zip'

    # Run from another working directory to check script-relative path handling.
    Push-Location $testRoot
    try {
        $result = & $packer -ManifestPath $manifestPath -OutputPath $outputPath
    } finally {
        Pop-Location
    }

    Assert-PackCheck ($result.FileCount -eq 2) 'Incorrect file count.'
    $zip = [IO.Compression.ZipFile]::OpenRead($outputPath)
    try {
        Assert-PackCheck ($zip.Entries.Count -eq 2) 'Unlisted files were included.'
        foreach ($file in $files) {
            $entry = $zip.GetEntry($file.path)
            Assert-PackCheck ($null -ne $entry) "Path was not preserved: $($file.path)"
            $stream = $entry.Open()
            $hasher = [Security.Cryptography.SHA256]::Create()
            try {
                $actualHash = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
                Assert-PackCheck ($actualHash -ceq $file.sha256) 'Archived bytes changed.'
            } finally {
                $hasher.Dispose()
                $stream.Dispose()
            }
        }
    } finally {
        $zip.Dispose()
    }

    $checksum = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $expectedChecksumText = "$checksum  assets.zip`n"
    Assert-PackCheck ([IO.File]::ReadAllText("$outputPath.sha256") -ceq $expectedChecksumText) 'ZIP checksum is incorrect.'

    # Refuse existing output files without changing their contents.
    Expect-PackFailure { & $packer -ManifestPath $manifestPath -OutputPath $outputPath }
    Assert-PackCheck ((Get-FileHash -LiteralPath $outputPath).Hash.ToLowerInvariant() -ceq $checksum) 'Existing ZIP was overwritten.'
    $failedOutput = Join-Path $testRoot 'output/failed.zip'
    [IO.File]::WriteAllText("$failedOutput.sha256", 'existing checksum')
    Expect-PackFailure { & $packer -ManifestPath $manifestPath -OutputPath $failedOutput }
    Assert-PackCheck ([IO.File]::ReadAllText("$failedOutput.sha256") -ceq 'existing checksum') 'Existing checksum was overwritten.'
    Remove-Item -LiteralPath "$failedOutput.sha256"

    # A changed source must fail without refreshing the manifest or publishing a ZIP.
    [IO.File]::WriteAllText($firstSource, 'changed test asset')
    Expect-PackFailure { & $packer -ManifestPath $manifestPath -OutputPath $failedOutput }
    Assert-PackCheck (-not (Test-Path -LiteralPath $failedOutput)) 'A failed pack left a ZIP.'
    Assert-PackCheck ([IO.File]::ReadAllText($manifestPath) -ceq $manifestText) 'Manifest was changed.'
    [IO.File]::WriteAllText($firstSource, 'first test asset')

    # Reject missing files, duplicate paths and paths outside the repository.
    $badEntries = @(
        @(@{ path = '../outside.blend'; sha256 = $files[0].sha256 }),
        @(@{ path = $firstSource; sha256 = $files[0].sha256 }),
        @(@{ path = 'missing-developer-asset.blend'; sha256 = $files[0].sha256 }),
        @($files[0], $files[0]),
        @(@{ path = $files[0].path; sha256 = 'invalid' })
    )

    foreach ($entries in $badEntries) {
        @{ schema = 1; files = @($entries) } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath
        Expect-PackFailure { & $packer -ManifestPath $manifestPath -OutputPath $failedOutput }
    }

    foreach ($badManifest in @('{"schema":2,"files":[]}', '{"schema":1,"files":[]}', 'not json')) {
        [IO.File]::WriteAllText($manifestPath, $badManifest)
        Expect-PackFailure { & $packer -ManifestPath $manifestPath -OutputPath $failedOutput }
    }

    Assert-PackCheck (-not (Test-Path -LiteralPath $failedOutput)) 'Invalid inputs produced a ZIP.'

    # Packing the same inputs twice should produce the same archive checksum.
    [IO.File]::WriteAllText($manifestPath, $manifestText)
    $repeat = & $packer -ManifestPath $manifestPath -OutputPath (Join-Path $testRoot 'output/repeat.zip')
    Assert-PackCheck ($repeat.Sha256 -ceq $result.Sha256) 'Unchanged inputs produced different ZIP bytes.'
    Assert-PackCheck (@(Get-ChildItem -LiteralPath (Join-Path $testRoot 'output') -Force -Filter '*.tmp').Count -eq 0) 'Temporary files were left behind.'

    Write-Host 'DEVELOPER_ASSET_PACK_TESTS_PASSED'
} finally {
    # Delete only this test run's uniquely named directory inside the workspace.
    $resolvedRoot = [IO.Path]::GetFullPath($testRoot)
    $allowedRoot = [IO.Path]::GetFullPath($scratchRoot) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedRoot.StartsWith($allowedRoot) -or (Split-Path -Leaf $resolvedRoot) -notlike 'pack-assets-test-*') {
        throw 'Unsafe pack test cleanup target.'
    }
    Remove-Item -LiteralPath $resolvedRoot -Recurse
}
