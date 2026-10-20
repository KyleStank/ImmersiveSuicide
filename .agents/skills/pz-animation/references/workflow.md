# Supported workflow

Paths below are skill-relative unless marked repository-relative.
Tested locally with Blender5.2.2 LTS, Paddlefruit V4 and PZ Build42 on Windows.

## One command

### First-time setup after cloning

Requires PowerShell 7 and a compatible Blender installation (tested with 5.2.2
LTS). From repository root run:

```powershell
./initialize.ps1
```

Setup uses `blender` from PATH if present, otherwise prompts for its executable's
absolute path. It checks `--version` and writes ignored root
`.immersive-suicide.local.json` (schema 1, `blender_path`, optional
`project_zomboid_path`), then restores developer assets from Google Drive using
`scripts/restore-developer-assets.ps1`. All files must match the local manifest
hashes before they overwrite existing developer assets, including local edits.
Setup does not install software or copy the mod into the game. Use
`-SkipAssetRestore` for offline/configuration-only setup. If a download fails, the
saved configuration remains available; retry the restore script directly.
The dot-prefixed filename is local configuration, not a committed recipe; Windows
Explorer may still show it. Never commit another machine's paths.

For explicit, noninteractive setup, provide `-BlenderPath` and optionally
`-ProjectZomboidPath`, using absolute native paths. The game path must be the
installation containing `media/`, not the save/mods directory. Use `-Force` to
deliberately replace an existing configuration; omitted game path then becomes null.
These reruns restore assets too unless `-SkipAssetRestore` is supplied.
Reinitialize after moving installations or copying the checkout to another machine.
Exports and starter recipes do not require a game installation. External game
assets are required only for optional new item previews and diagnostics.

Both toolkit and integration tests read this config. `-BlenderPath` on either
command overrides it for one run and permits Blender-only use without setup.
Repository paths are derived from script locations, not a particular username,
drive, checkout directory or caller's working directory. Only Windows has been
verified; configurable paths are not proof of cross-platform Blender/native support.

### Author, retime or export

From repository root:

```powershell
$tool = './.agents/skills/pz-animation/scripts/animation-toolkit.ps1'
& $tool assets/specs/hand-gesture.json -Name Bob_IS_MyGesture
& $tool assets/specs/retime.json -Operation retime -Name Bob_IS_MyTiming
& $tool assets/specs/export-final.json -Operation export -Name Bob_IS_MyExport
```

- `template`: copy the immutable rig and author a sparse schema1 recipe.
- `retime`: copy an existing blend and apply a strictly increasing time map,
  checking corresponding poses at subframes.
- `export`: copy and export an existing editable blend without retiming it.

`-BlenderPath` overrides the local configuration. Recipe paths may be absolute,
repository-relative or skill-relative. Inside recipes, `skill:` and `repo:`
prefixes resolve independent of file location; other paths resolve relative to
the recipe. `extends` merges objects shallowly; arrays replace rather than merge.
For `held_item_preview.mesh_path` and `.texture_path`, use `game:media/...` to
resolve a file inside the configured game installation, or a recipe-relative path.
Escaping the game directory is rejected. Keep machine-specific absolute paths out
of shared recipes. Generated reports may record resolved local paths.

Every review needs a new name. Failed attempts are preserved too: inspect them
and choose a new name instead of deleting a possible manual edit. Results go only
to ignored `work/output/<name>/`: editable blend, GLB, previews, resolved recipe,
validation and build record. The command checks copied/protected inputs, GLB
structure and a read-only reimport position comparison before optional staging.

For the fixed kitchen-knife grip, add
`-GripReference skill:assets/examples/short-blade-one-hand/03-approved-finger-grip.blend`.
This additionally checks hand-relative prop/thumb/finger transforms across the
clip. It is not a general grip solver for every weapon.

For a head-stab review export, use `assets/specs/export-head-stab.json` with
`-Operation export` and a new name. See the [head-stab guide](examples/head-stab.md)
for its single-key grip layout and validation limits.

## Review and promotion

Inspect front/right poses and interpolated motion. User feedback should describe
what looks wrong in everyday language. A single corrected saved pose can become
a reusable grip or target; do not require manual corrections on every frame.

`-Stage` explicitly copies a NEW verified GLB into workspace Build42
`Contents/mods/ImmersiveSuicide/42.0/media/anims_X/Bob/`. It refuses an existing
destination. It does not install the mod, change Lua gameplay, or authorize
overwriting an already-approved asset. The maintainer handles local installation.

After explicit final approval, copy the exact reviewed blend to repository
`animation/<clip>.blend` and verify identical hashes. Blender `.blend1` backups
may be present alongside these sources; the production-folder test ignores them. Keep the skill's
`assets/references.json` registry limited to its frozen reusable assets; production
sources can be renamed or edited independently. Never automatically promote a draft or overwrite
an approved source. Game exports remain in the mod's media tree, not animation/.

## Deliberate contents

- `scripts/blender/`: reusable authoring, curve operations and checks.
- `scripts/diagnostics/`: optional Java format/Lua troubleshooting.
- `assets/rig/`: immutable rig template. Optional Blender backups are not registered or tested.
- `assets/specs/`: maintained template, retime and frozen-example export recipes.
- `assets/examples/<animation>/`: curated numbered milestones, frozen reference
  exports and small verification records. Numbering restarts at `01` per animation.
- `assets/examples/<animation>/construction/`: guarded reference-only builders
  and helpers. Shared curve math lives in `scripts/blender/motion_curves.py`.
- `assets/references.json`: small curated approval/integrity registry, not a
  generated repository inventory.
- `work/`: ignored generated files. It is not a backup.

Binary assets need backup/versioning (possibly Git LFS) and may have rig/game
redistribution restrictions. Nothing here installs packages, configures Git/LFS,
commits files, or deploys an installed mod.

## Checks

Fast dependency-free checks (Python 3.11+, or run with Blender's Python):

```powershell
python -B .agents/skills/pz-animation/tests/test-animation-toolkit.py
```

Full local verification (Blender, no game startup; creates then removes its own
uniquely named test drafts, retains failures for diagnosis):

```powershell
./.agents/skills/pz-animation/tests/test-animation-toolkit.ps1
```

This exercises schema/path guards, template generation, retiming, approved-source
export, fixed grip, golden GLB channels, protected hashes, and overwrite/failure
handling. Results go in ignored work/. Both frozen final exports are checked for motion parity. There is no inventory regeneration step.

## Scope

Supported does not mean automatically realistic. Export parity checks integer-frame
joint positions, not every rotation or skin vertex; golden comparisons check exact
exported channels for the approved regression case. Collisions, contact and motion
quality still need visual/in-game review. General full-body authoring still requires
AI pose decisions and iteration; the construction references are not production
operators with universal frame numbers.
