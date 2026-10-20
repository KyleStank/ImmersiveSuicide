[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/N4N61AUUX0)

# Immersive Suicide

Project Zomboid mod that adds an immersive character suicide option using firearms
and, in Build 42, one-handed short blades with a custom animation. Custom animations
are developed through an AI-assisted Blender workflow.

## Supported builds

- **Build 42:** active development, including all new features and custom animations.
- **Build 41:** pure maintenance mode; changes only when explicitly requested.

The runtime mod ID is `stanks_suicide`. Check each build's `mod.info` for its
declared minimum version. Build 42 development does not require tracking B41/B42
differences.

## Working on this project

Start with [AGENTS.md](AGENTS.md) for the AI/maintainer working agreement and
[ARCHITECTURE.md](ARCHITECTURE.md) for the actual mod layout and runtime flow.
All three documents are maintained alongside implementation changes.

Build 42 runtime files are under `Contents/mods/ImmersiveSuicide/42.0/`.
The similarly named unversioned `media/` directory is the legacy Build 41 tree.
The game loads the Lua/XML/media content directly.

For local testing, use a compatible Project Zomboid installation and a disposable
test character/save. The maintainer installs the updated local mod and launches
the game in debug mode. Confirm the Build 42 content is installed before testing.
AI agents do not install or publish changes without authorization. Check the game console/logs
and the affected behavior; client/server changes need relevant multiplayer testing.

## Runtime development

Build 42 uses a shared base timed action with firearm and melee subclasses.
`42.0/media/lua/shared/ImmersiveSuicide/ImmersiveSuicideDefinitions.lua` selects each
animation's target body part and bullet effect; `ImmersiveSuicideOutcome.lua` applies common death
and sandbox rules on both client and server. The inventory menu and action
selection use the shared definitions to find supported animations; multiple matching
animations are chosen at random. Melee eligibility currently requires
one-handed short blades (`WeaponCategory.SMALL_BLADE`). The `excludedWeapons`
lookup in `ImmersiveSuicideDefinitions.lua` excludes 25 utensils, pointed tools
and blunt items from that category. Add full item IDs under the relevant weapon-kind
constant to extend it. A weapon kind without an exclusion group has no item exclusions.
Restart both client and server after changing the list.

For repeated melee impacts, add `impactCount` to the animation's shared definition
and one XML `impactTime` event per hit, with `m_ParameterValue` set to `1`, `2`, etc.
Each number runs once per action. Existing definitions default to one impact;
missing/empty parameters mean impact 1. The second short-blade animation uses
three events at `m_TimePc` values `0.23`, `0.38`, `0.54`; adjust these in
`42.0/media/AnimSets/player/actions/IS_ShortBladeOneHand2.xml` to tune contact timing.
Keep `killTime` as the separate final death event. Firearms remain single-shot.

With a JDK on PATH and the game path configured, run isolated behavioral checks:

```powershell
./tests/test-runtime.ps1
```

Use `-JavaPath /path/to/jdk/bin/java` if the default Java command does not select
your JDK. When updating an installed copy, remove the obsolete Build 42
`lua/client/Actions/SuicideTimedAction.lua`; its replacement is the three new
action files, and leaving it installed would retain its old network handler.

The checks use the game's Kahlua VM and base classes with mocked game services;
they do not start the game, use saves or verify playback/network synchronization.
After installing locally, test handgun/rifle and knife playback, impact/death timing,
empty/jammed firearms, hammer exclusion, unequipped weapons, cancellation by
movement/aim, both confirmation settings and both forced-zombification settings.
Repeat in multiplayer with an observing client, checking bullet effects and death.
All peers need this version: death messages now carry an animation definition ID.
Existing animations still target the head; torso support is configurable data.

## Project initialization

From repository root, initialize the machine using PowerShell 7
(Blender must already be installed):

```powershell
./initialize.ps1
```

This discovers Blender on PATH or prompts for its absolute executable path and
writes git-ignored `.immersive-suicide.local.json`, then calls the developer-asset
restore script to download and validate the listed assets. Optionally pass
`-ProjectZomboidPath` with the absolute game installation directory for item
previews/diagnostics; it is not needed for ordinary exports. See the skill's
[setup instructions](.agents/skills/pz-animation/references/workflow.md#first-time-setup-after-cloning)
for additional animation-specific details. All project skills read this same
configuration. The shared PowerShell reader is `scripts/project-config.ps1`.

Configuration schema 1 contains `blender_path` and optional
`project_zomboid_path`. For noninteractive setup pass `-BlenderPath` and optionally
`-ProjectZomboidPath` with native absolute paths. The game directory must contain
`media/`, not be the user save/mods directory. Setup checks Blender's identity via
`--version`; it does not install software. Developer assets are downloaded after
configuration is saved. Use `-Force` to deliberately replace an existing config; omitting the game path then clears it.
Reinitialize for a different machine or installation location. Developer assets
are restored automatically during initialization. **This replaces existing
listed asset files, including local edits, after all downloaded hashes pass.** Use
`-SkipAssetRestore` for offline/configuration-only setup, including configuration
updates with `-Force`. If restoration fails, initialization fails but retains the
saved configuration; retry with `./scripts/restore-developer-assets.ps1` without
rewriting configuration. Initialization tests use isolated fixtures:

```powershell
./tests/test-initialize.ps1
```

[developer-assets.json](developer-assets.json) lists files used for development,
with repository-relative paths and SHA-256 hashes. Developer assets can use any
file format; the manifest includes production Blender sources, the rig, and
frozen numbered examples with reference GLBs for both animations. A file's purpose
determines whether it belongs here, rather than its extension. Build 42 runtime GLBs are game
assets and are not included. Backups and generated drafts are also excluded.
The restore script downloads the manually uploaded Google Drive bundle and
validates its files against this local manifest.

## Animation development

Final editable `.blend` sources live in `animation/`. Blender `.blend1` backups
are optional and ignored by the production-folder check. Final exported character
`.glb` files live in `Contents/mods/ImmersiveSuicide/42.0/media/anims_X/Bob/`.
The maintainer's second production source is `animation/Bob_IS_ShortBladeOneHand2.blend`;
its separately renamed/exported runtime clip is `Bob_IS_ShortBladeOneHand2`.
Its XML action and shared definition make it available alongside the first
short-blade animation. In-game playback and sound verification remain pending.

Tools, reusable examples and working drafts live inside the
[animation skill](.agents/skills/pz-animation/SKILL.md), not the production source folder.

Use the skill's [workflow](.agents/skills/pz-animation/references/workflow.md) for
authoring/export commands and prerequisites. The workflow has been tested locally
with Blender 5.2.2 LTS and Paddlefruit V4. Never modify or directly open its original
rig; always work on a copy. The maintainer reviews motion in Blender and in-game,
and can optionally correct a single pose; animation expertise is not expected.

Frozen learning milestones are grouped under `assets/examples/short-blade-one-hand/`
and `assets/examples/head-stab/` inside the skill. Each sequence starts at `01`;
the [example guides](.agents/skills/pz-animation/references/motion-and-validation.md#choosing-an-example)
explain what to reuse and which review status applies. Production sources remain separate.

Fast toolkit checks require Python 3.11 or newer (or the supported Blender's Python):

```powershell
python -B .agents/skills/pz-animation/tests/test-animation-toolkit.py
```

The full Blender integration checks use the installed Blender path or an explicit
`-BlenderPath` override:

```powershell
./.agents/skills/pz-animation/tests/test-animation-toolkit.ps1
```

These checks do not start the game or validate gameplay. In debug Animation Viewer,
open **Options** and check **Immersive Suicide: Show Debug UI** to reveal the
kitchen-knife preview button. This option defaults to off for each new viewer;
turning it off hides the button and knife model.

## Packaging and Workshop maintenance

Create a developer-asset ZIP from the checked-in manifest with PowerShell 7:

```powershell
./scripts/pack-developer-assets.ps1
```

This creates `artifacts/developer-assets.zip` and `artifacts/developer-assets.zip.sha256`.
It verifies the manifest hashes, preserves repository-relative paths, and checks the
archived bytes before publishing the local output files. Only listed files are included;
packing and restoration work with any file format listed in the manifest.
The manifest itself and unlisted backups are not included. Blender/game setup is not required.
Sources and manifest hashes are never changed. Existing ZIP/checksum files are not overwritten.
For another bundle, supply a new name with `-OutputPath ./artifacts/developer-assets-v1.zip`.
An alternate manifest can be supplied with `-ManifestPath`; its asset paths remain relative
to the repository root. All files under `artifacts/` are generated and ignored by Git.

Upload the ZIP and checksum to Google Drive manually. The packer has no upload code.

Restore developer assets from the configured Google Drive link:

```powershell
./scripts/restore-developer-assets.ps1
```

**Restoration overwrites existing files at every listed destination, including local edits.**
The script downloads into a temporary folder under `artifacts/`, checks ZIP paths,
unpacks, and compares every file's SHA-256 with the local manifest. Any hash failures
are reported together; no destination files change unless all files pass validation.
After validation it moves the files into their manifest paths, then deletes the
downloaded ZIP, unpacked folders and temporary rollback copies. If a move fails, it
attempts to restore previous files; an incomplete rollback retains its recovery files
and reports their location.

`-DestinationRoot` selects another restore folder. `-SourceUrl` overrides the HTTPS
source link. For offline use, `-ArchivePath ./artifacts/developer-assets.zip` uses a
local ZIP; that original ZIP is preserved. `-ManifestPath` selects another trusted
local manifest. Unpacked data is limited to 4 GiB by default; use
`-MaximumUnpackedBytes` to change the limit. Google Drive must allow the download
without signing in; a sign-in/confirmation page is reported as an invalid ZIP.

```powershell
./tests/test-restore-developer-assets.ps1
```

Run the packer tests using small temporary fixtures:

```powershell
./tests/test-pack-developer-assets.ps1
```

The playable mod uses a separate packaging command. From repository root, `bash scripts/pack.sh` recreates `dist/` and copies runtime
mod content into it. It deletes the previous `dist/`; it does not export animations,
run tests or publish. Inspect the result before uploading.

`scripts/workshop-upload.vdf` and `scripts/set-thumbnail.vdf` contain placeholder
paths that must be set locally. The upload VDF expects `dist/preview.gif`, which
the pack script does not prepare. Do not assume packaging produces a ready upload.

To update the Workshop preview with SteamCMD, set `previewfile` in
`scripts/set-thumbnail.vdf` to the absolute path of `preview.gif`, authenticate
interactively, then run `workshop_build_item` with the VDF's absolute path.
Do not store credentials in files or chat. Workshop uploads require explicit
maintainer authorization and are separate from local testing and packaging.
