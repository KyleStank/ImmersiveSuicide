# Head-stab example

Use this example for a right-hand short-blade lift, three repeated strokes and
a full-body backward fall. Frozen assets live in `assets/examples/head-stab/`.
The maintainer visually approved the rendered sequence. In-game verification
has not been reported; do not label it in-game approved.

| Milestone | Source review | What to inspect |
| --- | --- | --- |
| `01-manual-lift.blend` | `Bob_IS_HeadStab_ManualRevision01` | Corrected lift through frame 17. Preserve this prefix; later motion was removed by the maintainer. |
| `02-manual-first-stab.blend` | `Bob_IS_HeadStab_Review05_Revised` | Frame 17 ready pose and frame 24 contact, deeper hand travel and elbow target. Later strokes in this file are superseded. |
| `03-approved-three-stabs.blend` | `Bob_IS_HeadStab_Review06` | Repeat the first hand/elbow stroke at frames 40 and 56; recover to the ready pose at 33 and 49. Wrist orientation stays fixed during the strokes. |
| `04-reviewed-backward-fall.blend` and `.glb` | `Bob_IS_HeadStab_Review13` | Preserve through frame 56, then fall using pelvis, spine, head, foot/knee targets, left FK arm and right IK arm. Still ending from frame 98 through 104, at 30 fps. |

`02-first-stab-controls.json` records extracted LOCAL hand/elbow transforms at
17 and 24. `04-validation.json` records the actual preservation, grip, reach,
ending-hold and export checks. These are example-specific observations, not
universal frame numbers or a collision guarantee.

## Construction techniques

- `construction/repeat_first_stab.py`: copy first-stroke values AND Bezier handles,
  shift their times for later strokes, and return the elbow target to the corrected
  ready pose between strokes. Validate the complete approved prefix at subframes.
- `construction/append_backward_fall.py`: match the evaluated spine before using
  direct spine keys in a copied rig, transfer sparse native reference poses, carry
  the knife arm with the pelvis while withdrawing it, and use the active leg IK
  targets. Ground adjustment follows the arm correction. Check reach between keys.
- `construction/native_death_reference.py`: narrow text-X skeleton sampler for
  the installed `Zombie_Death` reference. It reads game files locally; no base-game
  death asset is bundled. It is not a general animation importer.

These files are guarded construction references, not supported build commands.
Adapt them to new motion instead of replaying their fixed timing or copying rig
constraint changes into unrelated animations. Their source paths use frozen
milestones rather than ignored draft folders. Shared math remains in the toolkit.

## Native backward-death reference


The installed Build 42 player node `media/AnimSets/player/death/default.xml`
selects `Zombie_Death` at speed scale `0.80`. Its source is
`game:media/anims_X/Zombie/Zombie_Death.X`: a full-body backward fall and settling
motion. Check the node in the targeted installation before relying on this name
or timing after game updates. This differs from the rig's static, face-down
`DeadDown` reference.

When transferring full-body motion to V4, account for the chest-driven
COPY_ROTATION constraints on `CTRL-Spine1` and `CTRL-Spine2`; directly adding
reference rotations can fold the torso too far. If a review copy uses direct spine
keys instead, first match the evaluated spine pose and verify the approved prefix
at subframes. Never change the immutable rig to accommodate a draft.

Inspect the active IK switches before choosing leg controls. With leg IK enabled,
foot and knee targets drive the pose; FK leg keys do not produce the intended
motion. Carry root-space limb targets with the falling body and check arm reach
between authored poses as well as at the poses themselves. Native reference
sampling and export checks still require visual and in-game review.

## Frozen example versus production

The frozen blend/action/export still uses `Bob_IS_HeadStab_Review13`. The maintainer
saved a separate production source as `animation/Bob_IS_ShortBladeOneHand2.blend`,
renamed its action and exported `Bob_IS_ShortBladeOneHand2.glb` into the Build 42
runtime tree. Do not rename the frozen example or replace either production file
when studying it. Production files are intentionally excluded from the skill
registry; the source blend belongs in the developer-asset manifest, while the
runtime GLB does not. This does not establish gameplay XML integration.

To export a new review copy through the supported toolkit, use
`assets/specs/export-head-stab.json` with `-Operation export` and a NEW `Bob_` name.
The example retains the maintainer's constant single-key prop curves. The optional
`-GripReference` check expects the first example's two-key layout; for this example
compare hand-relative prop/thumb/finger matrices directly against its saved pose.
Read the saved reference before changing frames, which can reevaluate older keys.
