#requires -Version 7.0
[CmdletBinding(DefaultParameterSetName = 'Download')]
param(
    [string]$ManifestPath = "$PSScriptRoot/../developer-assets.json",
    [string]$DestinationRoot = "$PSScriptRoot/..",

    [Parameter(ParameterSetName = 'Download')]
    [uri]$SourceUrl = 'https://drive.google.com/file/d/1su58MYayjE6fk1IAlcKfvgkP2TFizcDY/view?usp=drive_link',

    [Parameter(Mandatory, ParameterSetName = 'Local')]
    [string]$ArchivePath,

    [long]$MaximumUnpackedBytes = 4GB
)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$destination = [IO.Path]::GetFullPath($DestinationRoot)
$comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
$comparer = if ($IsWindows) { [StringComparer]::OrdinalIgnoreCase } else { [StringComparer]::Ordinal }

function Get-AssetPath {
    param([string]$Root, [string]$RelativePath)

    $parts = $RelativePath.Split('/')
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or
        [IO.Path]::IsPathRooted($RelativePath) -or $RelativePath -match '[\\:\x00-\x1F]' -or
        $parts -contains '' -or $parts -contains '.' -or $parts -contains '..') {
        throw "Invalid asset path: $RelativePath"
    }

    $fullPath = [IO.Path]::GetFullPath((Join-Path $Root $RelativePath))
    $prefix = $Root.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($prefix, $comparison)) {
        throw "Asset path escapes its destination: $RelativePath"
    }
    return $fullPath
}

function Assert-AssetDestination {
    param([string]$RelativePath)

    # Check existing directories as well as the final file, without following links.
    $current = $destination
    $parts = @('') + $RelativePath.Split('/')
    for ($index = 0; $index -lt $parts.Count; $index++) {
        if ($parts[$index]) { $current = Join-Path $current $parts[$index] }
        if (-not (Test-Path -LiteralPath $current)) { continue }

        $item = Get-Item -LiteralPath $current -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Destination contains a link: $current"
        }
        if ($index -lt $parts.Count - 1 -and -not $item.PSIsContainer) {
            throw "Destination directory is a file: $current"
        }
        if ($index -eq $parts.Count - 1 -and $item.PSIsContainer) {
            throw "Destination file is a directory: $current"
        }
    }
}

# Read the trusted local manifest. Nothing in the download chooses destination paths.
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json -AsHashtable
if ($manifest -isnot [Collections.IDictionary] -or
    ($manifest.schema -isnot [int] -and $manifest.schema -isnot [long]) -or
    $manifest.schema -ne 1 -or $manifest.files -isnot [array] -or $manifest.files.Count -eq 0) {
    throw 'Expected manifest schema 1 with a non-empty files array.'
}
if ($MaximumUnpackedBytes -le 0) { throw 'MaximumUnpackedBytes must be positive.' }

$assets = [Collections.Generic.Dictionary[string, object]]::new($comparer)
$allowedDirectories = [Collections.Generic.HashSet[string]]::new($comparer)
foreach ($file in $manifest.files) {
    if ($file -isnot [Collections.IDictionary] -or $file.path -isnot [string] -or
        $file.sha256 -isnot [string] -or $file.sha256 -notmatch '^[a-fA-F0-9]{64}$') {
        throw 'Each manifest entry must have a path and a SHA-256 hash.'
    }

    $target = Get-AssetPath $destination $file.path
    if ($assets.ContainsKey($file.path)) { throw "Duplicate manifest path: $($file.path)" }
    $assets.Add($file.path, [pscustomobject]@{
        RelativePath = $file.path
        Destination = $target
        Sha256 = $file.sha256.ToLowerInvariant()
        Staged = $null
        Backup = $null
        Existed = $false
    })

    $parent = $file.path
    while ($parent.Contains('/')) {
        $parent = $parent.Substring(0, $parent.LastIndexOf('/'))
        [void]$allowedDirectories.Add($parent)
    }
}

$artifactRoot = Join-Path $repoRoot 'artifacts'
$workRoot = Join-Path $artifactRoot ('.restore-developer-assets-' + [guid]::NewGuid().ToString('N'))
$downloadPath = Join-Path $workRoot 'download.zip'
$unpackedRoot = Join-Path $workRoot 'unpacked'
$backupRoot = Join-Path $workRoot 'previous-files'
$attempted = [Collections.Generic.List[object]]::new()
$keepWorkFiles = $false
New-Item -ItemType Directory -Path $unpackedRoot -Force | Out-Null

try {
    if ($PSCmdlet.ParameterSetName -eq 'Local') {
        # Copy the supplied ZIP so cleanup never deletes the caller's archive.
        [IO.File]::Copy([IO.Path]::GetFullPath($ArchivePath), $downloadPath, $false)
    } else {
        if ($SourceUrl.Scheme -ne 'https') { throw 'SourceUrl must use HTTPS.' }
        $downloadUrl = $SourceUrl.AbsoluteUri
        if ($SourceUrl.Host -eq 'drive.google.com' -and $SourceUrl.AbsolutePath -match '^/file/d/([A-Za-z0-9_-]+)(?:/|$)') {
            $fileId = $Matches[1]
            $downloadUrl = "https://drive.usercontent.google.com/download?id=$fileId&export=download&confirm=t"
        }

        Write-Host 'Downloading developer assets...'
        Invoke-WebRequest -Uri $downloadUrl -OutFile $downloadPath -TimeoutSec 300 -MaximumRedirection 10
    }

    try {
        $zip = [IO.Compression.ZipFile]::OpenRead($downloadPath)
    } catch {
        throw 'The download is not a readable ZIP. Check the Google Drive link and sharing permissions; a sign-in or confirmation page cannot be restored.'
    }

    try {
        # Check the entire ZIP before extracting anything.
        $archiveErrors = [Collections.Generic.List[string]]::new()
        $seenFiles = [Collections.Generic.HashSet[string]]::new($comparer)
        $seenEntries = [Collections.Generic.HashSet[string]]::new($comparer)
        [long]$unpackedBytes = 0

        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName
            $isDirectory = $name.EndsWith('/')
            $relative = if ($isDirectory) { $name.TrimEnd('/') } else { $name }
            [void](Get-AssetPath $unpackedRoot $relative)
            if (-not $seenEntries.Add($relative)) { $archiveErrors.Add("Duplicate ZIP path: $name") }
            if ((($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000 -or
                ($entry.ExternalAttributes -band [IO.FileAttributes]::ReparsePoint)) {
                $archiveErrors.Add("ZIP links are not allowed: $name")
            }

            if ($isDirectory) {
                if (-not $allowedDirectories.Contains($relative)) { $archiveErrors.Add("Unlisted ZIP directory: $name") }
                continue
            }
            if (-not $assets.ContainsKey($name)) { $archiveErrors.Add("Unlisted ZIP file: $name") }
            [void]$seenFiles.Add($name)
            $unpackedBytes += $entry.Length
            if ($unpackedBytes -gt $MaximumUnpackedBytes) { throw 'ZIP exceeds MaximumUnpackedBytes.' }
        }

        foreach ($asset in $assets.Values) {
            if (-not $seenFiles.Contains($asset.RelativePath)) {
                $archiveErrors.Add("Missing ZIP file: $($asset.RelativePath)")
            }
        }
        if ($archiveErrors.Count) { throw ("ZIP validation failed:`n - " + ($archiveErrors -join "`n - ")) }

        foreach ($entry in $zip.Entries) {
            if ($entry.FullName.EndsWith('/')) { continue }
            $asset = $assets[$entry.FullName]
            $asset.Staged = Get-AssetPath $unpackedRoot $asset.RelativePath
            New-Item -ItemType Directory -Path (Split-Path -Parent $asset.Staged) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $asset.Staged, $false)
        }
    } finally {
        $zip.Dispose()
    }

    # Collect every hash failure before stopping. No destination files have changed yet.
    $hashErrors = [Collections.Generic.List[string]]::new()
    foreach ($asset in $assets.Values) {
        try {
            $actualHash = (Get-FileHash -LiteralPath $asset.Staged -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualHash -cne $asset.Sha256) {
                $hashErrors.Add("SHA-256 mismatch: $($asset.RelativePath) (expected $($asset.Sha256), actual $actualHash)")
            }
        } catch {
            $hashErrors.Add("Could not hash $($asset.RelativePath): $($_.Exception.Message)")
        }
    }
    if ($hashErrors.Count) {
        throw ("Developer asset validation failed. No destination files were changed:`n - " + ($hashErrors -join "`n - "))
    }

    # Preflight every destination, then save existing files for rollback if a move fails.
    foreach ($asset in $assets.Values) { Assert-AssetDestination $asset.RelativePath }
    foreach ($asset in $assets.Values) {
        $asset.Existed = Test-Path -LiteralPath $asset.Destination -PathType Leaf
        if ($asset.Existed) {
            $asset.Backup = Get-AssetPath $backupRoot $asset.RelativePath
            New-Item -ItemType Directory -Path (Split-Path -Parent $asset.Backup) -Force | Out-Null
            [IO.File]::Copy($asset.Destination, $asset.Backup, $false)
        }
    }

    try {
        foreach ($asset in $assets.Values) {
            Assert-AssetDestination $asset.RelativePath
            New-Item -ItemType Directory -Path (Split-Path -Parent $asset.Destination) -Force | Out-Null
            $attempted.Add($asset)
            [IO.File]::Move($asset.Staged, $asset.Destination, $true)
        }
    } catch {
        $moveError = $_
        foreach ($asset in $attempted) {
            try {
                if ($asset.Existed) {
                    $previousHash = (Get-FileHash -LiteralPath $asset.Backup -Algorithm SHA256).Hash
                    $currentHash = if (Test-Path -LiteralPath $asset.Destination -PathType Leaf) {
                        (Get-FileHash -LiteralPath $asset.Destination -Algorithm SHA256).Hash
                    } else {
                        $null
                    }
                    if ($currentHash -cne $previousHash) {
                        [IO.File]::Copy($asset.Backup, $asset.Destination, $true)
                    }
                } elseif (Test-Path -LiteralPath $asset.Destination -PathType Leaf) {
                    Remove-Item -LiteralPath $asset.Destination
                }
            } catch {
                $keepWorkFiles = $true
                Write-Warning "Could not roll back $($asset.RelativePath). Previous files are retained under $backupRoot."
            }
        }
        throw $moveError
    }

    [pscustomobject]@{
        RestoredFiles = $assets.Count
        DestinationRoot = $destination
    }
} finally {
    # This directory belongs to this run and contains only downloads, unpacked files and rollback copies.
    if (-not $keepWorkFiles) {
        $resolvedWork = [IO.Path]::GetFullPath($workRoot)
        $allowedRoot = [IO.Path]::GetFullPath($artifactRoot) + [IO.Path]::DirectorySeparatorChar
        if (-not $resolvedWork.StartsWith($allowedRoot, $comparison) -or
            (Split-Path -Leaf $resolvedWork) -notlike '.restore-developer-assets-*') {
            throw 'Unsafe asset restore cleanup target.'
        }
        Remove-Item -LiteralPath $resolvedWork -Recurse -Force
    }
}
