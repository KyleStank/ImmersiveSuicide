#requires -Version 7.0
[CmdletBinding()]
param(
    [string]$ManifestPath = "$PSScriptRoot/../developer-assets.json",
    [string]$OutputPath = "$PSScriptRoot/../artifacts/developer-assets.zip"
)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pathComparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
$pathComparer = if ($IsWindows) { [StringComparer]::OrdinalIgnoreCase } else { [StringComparer]::Ordinal }

# Check the manifest before creating any output files.
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json -AsHashtable

if ($manifest -isnot [Collections.IDictionary] -or
    ($manifest.schema -isnot [int] -and $manifest.schema -isnot [long]) -or
    $manifest.schema -ne 1 -or $manifest.files -isnot [array] -or $manifest.files.Count -eq 0) {
    throw 'Expected manifest schema 1 with a non-empty files array.'
}

$seenPaths = [Collections.Generic.HashSet[string]]::new($pathComparer)
$assets = @(
    foreach ($file in $manifest.files) {
        if ($file -isnot [Collections.IDictionary] -or $file.path -isnot [string] -or
            $file.sha256 -isnot [string] -or $file.sha256 -notmatch '^[a-fA-F0-9]{64}$') {
            throw 'Each manifest entry must have a path and a SHA-256 hash.'
        }

        $relativePath = $file.path
        $parts = $relativePath.Split('/')

        if ([string]::IsNullOrWhiteSpace($relativePath) -or
            [IO.Path]::IsPathRooted($relativePath) -or $relativePath -match '[\\:\x00-\x1F]' -or
            $parts -contains '' -or $parts -contains '.' -or $parts -contains '..') {
            throw "Use a repository-relative path with forward slashes: $relativePath"
        }

        if (-not $seenPaths.Add($relativePath)) {
            throw "Duplicate asset path: $relativePath"
        }

        $sourcePath = [IO.Path]::GetFullPath((Join-Path $repoRoot $relativePath))

        if (-not $sourcePath.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, $pathComparison)) {
            throw "Asset path is outside the repository: $relativePath"
        }

        # Do not follow links to files outside the expected directory tree.
        $currentPath = $repoRoot
        foreach ($part in $parts) {
            $currentPath = Join-Path $currentPath $part
            $item = Get-Item -LiteralPath $currentPath -Force

            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Asset paths cannot contain links: $relativePath"
            }
        }

        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "Asset is not a file: $relativePath"
        }

        $expectedHash = $file.sha256.ToLowerInvariant()
        if ((Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedHash) {
            throw "Asset hash does not match the manifest: $relativePath. Review the asset before updating its manifest hash."
        }

        [pscustomobject]@{
            RelativePath = $relativePath
            SourcePath = $sourcePath
            Sha256 = $expectedHash
        }
    }
)

$archivePath = [IO.Path]::GetFullPath($OutputPath)
if ([IO.Path]::GetExtension($archivePath) -ine '.zip') {
    throw 'OutputPath must end in .zip.'
}

$checksumPath = "$archivePath.sha256"
if ((Test-Path -LiteralPath $archivePath) -or (Test-Path -LiteralPath $checksumPath)) {
    throw 'The ZIP or checksum already exists. Choose a new output name or move the old files first.'
}

$outputDirectory = Split-Path -Parent $archivePath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

# Build in temporary files so failed runs do not leave a finished-looking ZIP.
$runId = [guid]::NewGuid().ToString('N')
$temporaryArchive = Join-Path $outputDirectory ".developer-assets-$runId.zip.tmp"
$temporaryChecksum = Join-Path $outputDirectory ".developer-assets-$runId.sha256.tmp"
$archivePublished = $false
$complete = $false

try {
    $archiveStream = [IO.File]::Open($temporaryArchive, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    try {
        $zip = [IO.Compression.ZipArchive]::new($archiveStream, [IO.Compression.ZipArchiveMode]::Create, $true)
        try {
            foreach ($asset in $assets) {
                $entry = $zip.CreateEntry($asset.RelativePath, [IO.Compression.CompressionLevel]::Optimal)
                # File timestamps should not change the archive when the inputs are unchanged.
                $entry.LastWriteTime = [DateTimeOffset]'1980-01-01T00:00:00Z'
                $sourceStream = [IO.File]::Open($asset.SourcePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
                try {
                    $entryStream = $entry.Open()
                    try {
                        $sourceStream.CopyTo($entryStream)
                    } finally {
                        $entryStream.Dispose()
                    }
                } finally {
                    $sourceStream.Dispose()
                }
            }
        } finally {
            $zip.Dispose()
        }
    } finally {
        $archiveStream.Dispose()
    }

    # Check the actual archived bytes, including files changed during packing.
    $verificationZip = [IO.Compression.ZipFile]::OpenRead($temporaryArchive)
    try {
        if ($verificationZip.Entries.Count -ne $assets.Count) {
            throw 'The ZIP does not contain the expected number of assets.'
        }

        foreach ($asset in $assets) {
            $entry = $verificationZip.GetEntry($asset.RelativePath)
            if (-not $entry) { throw "Missing ZIP entry: $($asset.RelativePath)" }

            $entryStream = $entry.Open()
            $hasher = [Security.Cryptography.SHA256]::Create()
            try {
                $entryHash = [BitConverter]::ToString($hasher.ComputeHash($entryStream)).Replace('-', '').ToLowerInvariant()
                if ($entryHash -cne $asset.Sha256) {
                    throw "Archived asset hash does not match the manifest: $($asset.RelativePath)"
                }
            } finally {
                $hasher.Dispose()
                $entryStream.Dispose()
            }
        }
    } finally {
        $verificationZip.Dispose()
    }

    $archiveHash = (Get-FileHash -LiteralPath $temporaryArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksumText = "$archiveHash  $([IO.Path]::GetFileName($archivePath))`n"
    [IO.File]::WriteAllText($temporaryChecksum, $checksumText, [Text.UTF8Encoding]::new($false))

    # Move without overwriting, even if another file appeared while packing.
    [IO.File]::Move($temporaryArchive, $archivePath, $false)
    $archivePublished = $true
    [IO.File]::Move($temporaryChecksum, $checksumPath, $false)
    $complete = $true

    [pscustomobject]@{
        Archive = $archivePath
        ChecksumFile = $checksumPath
        Sha256 = $archiveHash
        FileCount = $assets.Count
        Bytes = (Get-Item -LiteralPath $archivePath).Length
    }
} finally {
    # Only remove this run's temporary files and an unfinished output pair.
    foreach ($temporaryPath in @($temporaryArchive, $temporaryChecksum)) {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath
        }
    }

    if ($archivePublished -and -not $complete) {
        Remove-Item -LiteralPath $archivePath
    }
}
