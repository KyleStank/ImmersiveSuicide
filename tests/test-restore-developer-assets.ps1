#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$restore = Join-Path $repoRoot 'scripts/restore-developer-assets.ps1'
$scratchRoot = Join-Path $repoRoot '_sandbox'
$testRoot = Join-Path $scratchRoot ('restore-assets-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null

function Assert-RestoreCheck {
    param($Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Expect-RestoreFailure {
    param([scriptblock]$Action)
    try {
        & $Action | Out-Null
    } catch {
        return $_.Exception.Message
    }
    throw 'Expected restore to fail.'
}

function New-TestArchive {
    param([string]$Path, [object[]]$Entries)

    $zip = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($item in $Entries) {
            $entry = $zip.CreateEntry($item.path)
            if ($item.link) { $entry.ExternalAttributes = 0xA000 -shl 16 }
            $writer = [IO.StreamWriter]::new($entry.Open(), [Text.UTF8Encoding]::new($false))
            try { $writer.Write($item.text) } finally { $writer.Dispose() }
        }
    } finally {
        $zip.Dispose()
    }
}

function Get-TextHash {
    param([string]$Text)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text))).Replace('-', '').ToLowerInvariant()
    } finally {
        $hasher.Dispose()
    }
}

try {
    # Fixture archives use tiny text files so the real developer assets stay untouched.
    $manifestPath = Join-Path $testRoot 'manifest.json'
    $entries = @(
        @{ path = 'animation/one.blend'; text = 'first approved asset' },
        @{ path = '.agents/skill/two.blend'; text = 'second approved asset' }
    )
    $manifest = @{
        schema = 1
        files = @(
            foreach ($entry in $entries) {
                @{ path = $entry.path; sha256 = Get-TextHash $entry.text }
            }
        )
    }
    $manifestText = $manifest | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($manifestPath, $manifestText)
    $archivePath = Join-Path $testRoot 'valid.zip'
    New-TestArchive $archivePath $entries
    $originalZipHash = (Get-FileHash -LiteralPath $archivePath).Hash

    # Existing local edits are overwritten only after the whole bundle passes validation.
    $destination = Join-Path $testRoot 'destination'
    New-Item -ItemType Directory -Path (Join-Path $destination 'animation') -Force | Out-Null
    $firstDestination = Join-Path $destination $entries[0].path
    [IO.File]::WriteAllText($firstDestination, 'old local version')
    $result = & $restore -ManifestPath $manifestPath -ArchivePath $archivePath -DestinationRoot $destination
    Assert-RestoreCheck ($result.RestoredFiles -eq 2) 'Wrong restored file count.'
    foreach ($entry in $entries) {
        Assert-RestoreCheck ([IO.File]::ReadAllText((Join-Path $destination $entry.path)) -ceq $entry.text) 'Asset was not restored to its manifest path.'
    }
    Assert-RestoreCheck ((Get-FileHash -LiteralPath $archivePath).Hash -ceq $originalZipHash) 'Local source archive was deleted or changed.'

    # Report both mismatches together and leave all destination files untouched.
    $badHashes = Join-Path $testRoot 'bad-hashes.zip'
    New-TestArchive $badHashes @(
        @{ path = $entries[0].path; text = 'wrong first bytes' },
        @{ path = $entries[1].path; text = 'wrong second bytes' }
    )
    [IO.File]::WriteAllText($firstDestination, 'preserve this local edit')
    $errorText = Expect-RestoreFailure { & $restore -ManifestPath $manifestPath -ArchivePath $badHashes -DestinationRoot $destination }
    foreach ($entry in $entries) {
        Assert-RestoreCheck ($errorText.Contains("SHA-256 mismatch: $($entry.path)")) 'Not all hash mismatches were reported.'
    }
    Assert-RestoreCheck ([IO.File]::ReadAllText($firstDestination) -ceq 'preserve this local edit') 'A hash failure changed existing assets.'

    # Missing, extra, duplicate, unsafe and link entries must not reach the destination.
    $invalidArchives = @(
        @($entries[0]),
        @($entries[0], $entries[1], @{ path = 'unlisted.blend'; text = 'extra' }),
        @($entries[0], $entries[1], $entries[0]),
        @($entries[0], $entries[1], @{ path = '../escape.blend'; text = 'escape' }),
        @(@{ path = $entries[0].path; text = 'link target'; link = $true }, $entries[1])
    )
    $number = 0
    foreach ($invalidEntries in $invalidArchives) {
        $invalidZip = Join-Path $testRoot "invalid-$number.zip"
        $number++
        New-TestArchive $invalidZip $invalidEntries
        [void](Expect-RestoreFailure { & $restore -ManifestPath $manifestPath -ArchivePath $invalidZip -DestinationRoot $destination })
        Assert-RestoreCheck ([IO.File]::ReadAllText($firstDestination) -ceq 'preserve this local edit') 'Invalid ZIP changed an existing asset.'
    }

    [void](Expect-RestoreFailure { & $restore -ManifestPath $manifestPath -ArchivePath $archivePath -DestinationRoot $destination -MaximumUnpackedBytes 1 })
    $html = Join-Path $testRoot 'signin.zip'
    [IO.File]::WriteAllText($html, '<html>Sign in</html>')
    $errorText = Expect-RestoreFailure { & $restore -ManifestPath $manifestPath -ArchivePath $html -DestinationRoot $destination }
    Assert-RestoreCheck ($errorText.Contains('not a readable ZIP')) 'Download-page error is unclear.'

    # Reject an unsafe local manifest before creating destination files.
    @{ schema = 1; files = @(@{ path = '../outside.blend'; sha256 = $manifest.files[0].sha256 }) } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath
    [void](Expect-RestoreFailure { & $restore -ManifestPath $manifestPath -ArchivePath $archivePath -DestinationRoot $destination })
    [IO.File]::WriteAllText($manifestPath, $manifestText)

    # A destination directory in place of a file must fail before changing any files.
    $blockedDestination = Join-Path $testRoot 'blocked'
    New-Item -ItemType Directory -Path (Join-Path $blockedDestination $entries[1].path) -Force | Out-Null
    [void](Expect-RestoreFailure { & $restore -ManifestPath $manifestPath -ArchivePath $archivePath -DestinationRoot $blockedDestination })
    Assert-RestoreCheck (-not (Test-Path -LiteralPath (Join-Path $blockedDestination $entries[0].path))) 'Destination preflight happened too late.'

    # Simulate a late move failure on Windows and check that earlier replacements are undone.
    if ($IsWindows) {
        $secondDestination = Join-Path $destination $entries[1].path
        [IO.File]::WriteAllText($firstDestination, 'original first file')
        [IO.File]::WriteAllText($secondDestination, 'original second file')
        $locked = [IO.File]::Open($secondDestination, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
        try {
            [void](Expect-RestoreFailure { & $restore -ManifestPath $manifestPath -ArchivePath $archivePath -DestinationRoot $destination })
        } finally {
            $locked.Dispose()
        }
        Assert-RestoreCheck ([IO.File]::ReadAllText($firstDestination) -ceq 'original first file') 'Earlier replacement was not rolled back.'
        Assert-RestoreCheck ([IO.File]::ReadAllText($secondDestination) -ceq 'original second file') 'Locked destination changed.'
    }

    Assert-RestoreCheck ([IO.File]::ReadAllText($manifestPath) -ceq $manifestText) 'Manifest was modified.'
    Write-Host 'DEVELOPER_ASSET_RESTORE_TESTS_PASSED'
} finally {
    $resolved = [IO.Path]::GetFullPath($testRoot)
    $allowed = [IO.Path]::GetFullPath($scratchRoot) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($allowed) -or (Split-Path -Leaf $resolved) -notlike 'restore-assets-test-*') {
        throw 'Unsafe restore test cleanup target.'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
