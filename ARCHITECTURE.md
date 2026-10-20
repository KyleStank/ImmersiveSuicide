# Immersive Suicide architecture

## Scope and document contract

This explains this repository's implementation of a Project Zomboid mod, not a
complete engine manual. Read [AGENTS.md](AGENTS.md) for maintenance rules and
[README.md](README.md) for development commands. Check claims against code and
observed game behavior; resolve disagreements and update these documents together.

The game supplies Lua APIs, events, UI classes, timed actions, animation playback
and networking. This project extends those systems; it is not a standalone app.
New development targets Build 42. The older Build 41 implementation is retained
in pure maintenance mode and is changed only when explicitly requested. Build 42
work does not require B41 compatibility tracking.

## Source and artifact ownership

| Location | Responsibility |
| --- | --- |
| `Contents/mods/ImmersiveSuicide/mod.info` and `media/` | Legacy Build 41 metadata and runtime content. |
| `Contents/mods/ImmersiveSuicide/42.0/mod.info` and `42.0/media/` | Build 42 metadata and runtime content. The folder name does not mean all 42.x APIs are identical; inspect `versionMin` and the tested game build. |
| `media/lua/client/` in the applicable build tree | Menu hooks, confirmation UI, timed actions and client-side event handling. |
| `media/lua/server/` | Multiplayer client-command handlers. |
| `42.0/media/lua/shared/ImmersiveSuicide/` | Animation definitions, weapon eligibility and common injury/death outcomes. |
| Legacy `media/lua/shared/Translate/` | Existing translations; there is currently no separate translation directory in the 42.0 tree. Verify loading in-game before relocating or adding version-specific text. |
| `media/sandbox-options.txt` | Sandbox option definitions for the applicable build. |
| `media/AnimSets/player/actions/` | XML animation nodes, action conditions, speed variables and animation events. |
| `42.0/media/anims_X/Bob/` | Exported custom character animation GLBs consumed by the game. |
| `animation/` | Final editable production Blender sources. |
| `.agents/skills/pz-animation/` | Authoring tools, documentation, immutable rig, curated frozen examples and ignored drafts. Not shipped mod content. |
| `initialize.ps1`, `scripts/project-config.ps1` | Project-wide initialization and shared local configuration access for all skills. |
| `developer-assets.json` | Repository-relative destinations and SHA-256 hashes for developer assets of any file format, including Blender sources and the skill regression-reference GLB. |
| `scripts/pack-developer-assets.ps1`, `scripts/restore-developer-assets.ps1`, `artifacts/` | Developer ZIP creation, download/validation/restoration and ignored generated or temporary files, separate from playable-mod packaging. |
| `tests/` | Mod runtime test runner, Lua fixtures and project-configuration tests. |
| `.agents/skills/pz-animation/tests/` | Animation-skill contract, Blender curve/integration and Lua syntax checks. |
| Other `scripts/`, `workshop.txt`, root preview images | Packaging and Workshop maintenance inputs. |
| `dist/` | Generated package output. |

`_sandbox/` contains local research, not runtime dependencies or packaged content.

## Current gameplay flow

The following paths are relative to the selected build's `media/` directory;
Build 42 is the active development implementation.

1. `lua/client/ContextMenu.lua` adds firearm and one-handed short-blade options,
   using shared matching definitions and a single option-creation path. Equipment
   checks and firearm shootability determine whether the option is disabled. `FirearmRadialMenuPatch.lua`
   extends the vanilla firearm radial menu and guards against installing twice.
   It uses the shared firearm/equipment checks before the vanilla `canShoot()`
   check; its option still calls the common confirmation and action selection code.
2. `lua/client/ImmersiveSuicide.lua` optionally opens `ISUI/ISYesNoDialog.lua`,
   randomly selects from the matching shared definitions when there is more than
   one choice, and queues `FirearmSuicideTimedAction` or
   `MeleeSuicideTimedAction`. Both inherit `BaseSuicideTimedAction` in `Actions/`;
   the base owns animation setup, speed, equipment validation and `killTime`.
3. `lua/shared/ImmersiveSuicide/ImmersiveSuicideDefinitions.lua` maps stable IDs to
   PerformingAction values, weapon kind/handedness, target body part and bullet
   effect. `ImmersiveSuicideWeaponKind.FIREARM` and `.SHORT_BLADE` are the named
   constants used in definitions and action eligibility comparisons.
   Definitions are kept in an ordered list, with an ID lookup for outcome/network
   handling. Adding a matching definition also makes it available to action selection.
   All current definitions target the head. A future torso animation can
   select `BodyPartType.Torso_Upper` or `Torso_Lower` without another action class.
   The shared short-blade predicate requires a non-ranged HandWeapon, neither
   two-hand flag, and `WeaponCategory.SMALL_BLADE`. `excludedWeapons` groups full
   item IDs by weapon kind; the short-blade group excludes the 25 listed utensils,
   pointed tools and blunt items. `isExcluded(item, weaponKind)` returns false for
   missing groups. `getMatchingIds()` checks exclusions once per menu/selection call;
   the firearm radial menu and server death-request handler check them at their
   entry points too. `matchesWeapon()` and timed-action `isValid()` do not check
   exclusions during playback. Exclusion changes require restarting the game/server.
4. XML nodes under `AnimSets/player/actions/` connect PerformingAction to clips
   and emit `impactTime` and `killTime`. The base action handles these events and
   calls the firearm or melee action's `performImpact()` method. The firearm action owns
   shootability checks, sound and ammunition; the melee action owns melee impact.
   Ammo availability is checked before shooting, not continuously after spending
   the round. Equipment and definition eligibility are checked throughout actions.
5. `lua/client/ImmersiveSuicideNetwork.lua` owns the single client network handler
   and common impact/death dispatch. Single-player calls the shared
   `lua/shared/ImmersiveSuicide/ImmersiveSuicideOutcome.lua` directly. Multiplayer sends
   `definitionId` to `lua/server/ImmersiveSuicideServer.lua`; the server validates
   the ID against the equipped weapon, applies that same outcome and broadcasts
   the ID for client processing. Unknown definitions are ignored. Outcome data
   comes from shared definitions, not arbitrary client-supplied body parts.

Command module `ImmersiveSuicide` and existing command/event strings are contracts
between files. Existing misspelled `recieve...` strings remain unchanged. Death
messages now require `definitionId` instead of `isFirearm`; multiplayer peers must
run the same mod version. Server/client outcomes share one implementation, including
infection time and sandbox handling. This is not a security audit: the server still
accepts client-triggered impact/death requests rather than tracking action progress.

Sandbox definitions and `SandboxVars.ImmersiveSuicide` govern confirmation and
forced zombification. Translation keys connect menus/dialogs to the translation
files. Comments should explain relevant Build 42 behavior; B41/B42 difference
tracking is no longer required.

## Animation authoring versus gameplay integration

The animation skill implements an AI-assisted, iterative workflow: author a small
draft, validate exports, get maintainer feedback, preserve manual corrections and
promote the approved editable source. It is not a trained motion model or an
automatic full-body/physics solver. Its numbered examples are selected learning
milestones, not a build chain to replay for every animation.

Production `.blend` sources belong in `animation/`; reusable frozen references
belong inside the skill. GLBs used by Build 42 belong in its `anims_X/Bob/` tree.
Blender filenames, action names, export names and XML identifiers are separate;
renaming a source alone does not migrate the runtime animation contract.

`42.0/media/lua/client/Debug/ISAnimationViewerKnifePreview.lua` extends the stock
viewer only in debug mode, adding a knife model on `Bip01_Prop1` without editing
base-game files. Viewer playback/prop approval is not gameplay integration.
The maintainer reports successful testing of the current functionality in both
single-player and multiplayer, including the custom kitchen-knife animation and
melee event timing. Future runtime changes still need relevant game testing.

The skill's registry and export regression recipe use frozen skill examples, not
mutable production filenames. Root `initialize.ps1` writes ignored root
`.immersive-suicide.local.json` with schema 1, Blender's executable and an optional
Project Zomboid installation directory. PowerShell entry points share validation
via `scripts/project-config.ps1`; Python resolves preview `game:` paths through the same
file and rejects paths escaping the game installation. Ordinary exports require
only Blender; optional item previews and Java diagnostics need game files.
Script-relative paths locate the checkout; `-BlenderPath` remains a per-run override.
Initialization is explicit after cloning, not a Git hook or automatic installation.
Configuration belongs to the project and is shared by every skill; its PowerShell
tests live in `tests/test-project-config.ps1`. Initialization calls `scripts/restore-developer-assets.ps1` after saving the
configuration, unless `-SkipAssetRestore` is supplied. Restoration errors propagate
while preserving the saved configuration for direct retry. Existing configuration
still requires `-Force`; reruns restore assets too unless explicitly skipped.
`tests/test-initialize.ps1` verifies call order, skipping, existing-config guards
and error propagation using copied scripts and stand-ins. `developer-assets.json`
inventories ten developer assets with SHA-256 hashes: nine maintained `.blend`
files and the skill's `07-approved-overlapping-collapse.glb` regression reference.
The manifest, packer and restorer do not restrict file extensions; assets belong
in this bundle because they support development, rather than because of their format.
Build 42 runtime GLBs under `Contents/` are game assets and stay outside this
manifest, along with backups and generated drafts.
`scripts/pack-developer-assets.ps1` validates the manifest and file hashes, rejects
unsafe/duplicate paths and links, and creates a ZIP with exactly the listed relative
paths. It verifies the archived bytes before publishing the ZIP and archive SHA-256
sidecar under ignored `artifacts/`. ZIP entry timestamps are fixed, so unchanged
inputs produce identical output on the same compression runtime. Existing outputs
are never overwritten; failed runs remove their temporary files. The script does
not modify inputs, refresh hashes, or use Blender/game configuration. Focused fixture
checks live in `tests/test-pack-developer-assets.ps1`. Developer uploads to the
maintainer's Google Drive are manual.

`scripts/restore-developer-assets.ps1` defaults to the supplied Google Drive share
link, converts it to a download URL, and stages the ZIP under an owned temporary
folder in `artifacts/`. A local ZIP can be supplied with `-ArchivePath` for offline
restoration/testing. The trusted local manifest controls all destinations. The
script rejects missing, unlisted, duplicate, unsafe and link entries and checks the
advertised unpacked size before extraction (4 GiB by default). It hashes every
unpacked file and reports all mismatches together before changing any destination.
It then preflights destinations and moves validated files with overwrite enabled,
including replacements of local edits, as requested by the maintainer. Previous
files are temporarily copied for rollback on move errors. Normal success/failure
cleans the download and unpacked files; incomplete rollback retains recovery data
and reports it. Process termination or power loss is not transactionally recovered.
`tests/test-restore-developer-assets.ps1` covers fixture-based restore/failure paths.
The supplied Google Drive ZIP was also restored and independently hash-verified in
a disposable destination. No uploads are automated; initialization calls the same
restore entry point without changing its validation/overwrite behavior.
The skill registry still describes frozen reference purposes and hashes; shared
entries must agree. Remote archive hashes/size are not yet recorded in the local
manifest; per-file SHA-256 validation remains the acceptance check.

## Verification and delivery boundaries

The skill's workflow documents its contract tests and Blender integration suite.
They cover paths, protected hashes, curve handling and export regression behavior;
they do not prove gameplay correctness, skin/contact quality or multiplayer behavior.
`tests/test-runtime.ps1` runs mocked Lua behavioral checks using the configured
game's Kahlua VM and actual base timed-action classes. It covers weapon eligibility,
concrete action construction/events, firearm ammunition gating, data-selected body
parts, sandbox outcomes, invalid requests and definition-ID network round trips.
These are isolated checks, not engine/gameplay tests. Runtime changes still need
relevant debug-game testing and console/log inspection.

Local installation is performed by the maintainer.
`scripts/pack.sh` copies the mod tree into a freshly recreated
`dist/mods/ImmersiveSuicide/`; it does not build animations, run tests or publish.
The Workshop upload VDF references `dist/preview.gif`, but pack.sh does not copy
that image. Upload paths/preview preparation therefore require deliberate review.
Workshop publication is a separate human-authorized operation.

When extending the mod, identify the build and entry point, follow the existing
responsibility boundaries, check affected XML/Lua/network/translation contracts,
and update this document when those boundaries or supported workflows change.
