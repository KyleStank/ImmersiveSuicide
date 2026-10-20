# Shared configuration helpers. Loading this script does not change the config file.
$ProjectConfigPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.immersive-suicide.local.json'))

function Get-ProjectLocalConfig {
    param(
        [string]$Path = $ProjectConfigPath
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'Project configuration missing. Run initialize.ps1 first, or pass -BlenderPath explicitly for a Blender-only command.'
    }

    # Read the JSON and check its fields before using any paths.
    $config = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json

    if ($null -eq $config -or $config -is [array]) {
        throw 'Project configuration must be an object.'
    }

    foreach ($key in $config.PSObject.Properties.Name) {
        if ($key -notin @('schema', 'blender_path', 'project_zomboid_path')) {
            throw "Unknown project configuration key: $key"
        }
    }

    if (($config.schema -isnot [int] -and $config.schema -isnot [long]) -or $config.schema -ne 1) {
        throw 'Unsupported project configuration schema; expected integer 1.'
    }

    Assert-ProjectLocalPath $config.blender_path Leaf 'blender_path'

    # The game path is optional. If present, it must point to the game installation.
    if ($null -ne $config.project_zomboid_path) {
        Assert-ProjectLocalPath $config.project_zomboid_path Container 'project_zomboid_path'

        if (-not (Test-Path -LiteralPath (Join-Path $config.project_zomboid_path 'media') -PathType Container)) {
            throw 'project_zomboid_path must be the game installation containing media/, not the user save/mods directory.'
        }
    }

    return $config
}

function Assert-ProjectLocalPath {
    param(
        $Value,
        [string]$Type,
        [string]$Label
    )

    # Check that the path is absolute and points to an existing file or folder.
    if ($Value -isnot [string] -or [string]::IsNullOrWhiteSpace($Value) -or
        -not [IO.Path]::IsPathFullyQualified($Value) -or
        -not (Test-Path -LiteralPath $Value -PathType $Type)) {
        throw "${Label} must be an existing, absolute local $Type path. Run initialize.ps1 to configure this machine."
    }
}

function Resolve-ProjectBlender {
    param(
        [string]$Override
    )

    # Use the supplied Blender path, or read it from the configuration.
    $value = if ($Override) {
        $Override
    } else {
        (Get-ProjectLocalConfig).blender_path
    }

    Assert-ProjectLocalPath $value Leaf 'blender_path'

    return (Resolve-Path -LiteralPath $value).Path
}
