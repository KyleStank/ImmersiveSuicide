# Motion editing and validation

All shared math is in `scripts/blender/motion_curves.py`, with synthetic Blender
tests in `../tests/test_retime_animation.py`. No production module imports a one-off
animation builder.

## Example progression

The numbered files in `assets/examples/` are selected milestones, in development
order, from building our first animation incrementally with AI drafts and human
feedback. They are not every revision, a directly replayable build chain, or a
collection where each file is wholly good or bad. Earlier examples isolate useful
parts; later examples add motion and expose different problems. File numbering
does not change action names inside Blender or clip names in the game.

| File stem | What to reuse or learn |
| --- | --- |
| `01-natural-reach-wrist` | Approved natural arm reach and wrist alignment; no complete knife action yet. |
| `02-manual-knife-placement` | Human-corrected attachment placement; intentional thumb clipping, not a finished finger grip. |
| `03-approved-finger-grip` | Approved prop/thumb/finger pose saved at frame 20; reusable local grip transforms. |
| `04-manual-early-motion` | Human corrections to the early motion through frame 38; the later original continuation was reported broken and is NOT an approved target. |
| `05-manual-wrist-blade-orientation` | Human correction to wrist/blade direction; learn orientation intent, not a universal anatomical wrist pose. |
| `06-manual-timing-before-handle-repair` | Human timing decisions before handle repair; moved keys alone do not guarantee valid Bezier timing. |
| `07-approved-overlapping-collapse` | Complete in-game-approved motion: arm recovery overlaps body collapse. Matching GLB is the golden export for regression checks. |

The AI must read the relevant lesson, inspect the needed curves/poses in a working
copy, and adapt them to the new motion. Merely storing these files does not train
the model or teach it which poses are wrong. Failure lessons are documented here
and in `rig-and-authoring.md`; do not infer failure labels for whole files.
For a new animation, repeat the small-draft/review/correction loop in `SKILL.md`,
not this specific sequence of knife milestones. Exact paths, roles and unchanged
content hashes are recorded in `assets/references.json`.

## Proven techniques

- `curves/sample/matrix_error`: Blender5 channelbags and fractional-frame pose
  comparisons. Compare approved prefixes/tails at subframes, not just key values.
- `freeze_and_trim/restore_prefix`: preserve existing Bezier geometry when trimming
  a hold. Keep incoming boundary handles; only outgoing transition handles may change.
- `retime_curve`: piecewise-affine time mapping with de Casteljau splitting where
  needed. Map each handle on its segment's slope. Constant tracks need no added keys.
- `repair_curve_handles`: with an exact pre-edit curve correspondence, restore
  handle offsets and scale them by adjacent edited intervals without moving keys.
  Manually moving FREE keys can otherwise leave overlapping time handles.
- `smooth_monotone`: constrain scalar overshoot with sparse keys; not a guarantee
  of smooth quaternion angular speed, anatomical motion, or mesh clearance.

## Full-body construction examples

These four files under `assets/examples/construction/` preserve techniques from
the successful knife animation. Their direct-launch guards deliberately reject
historical recipe replay. They are learning material to adapt, not toolkit commands.

- `append_recovery.py`: knife clearance before wrist unwinding, preserving the
  approved prefix and the hand-relative grip.
- `append_kneel.py`: root-parented limb targets, pelvis descent, evaluated toe
  pivots and mild torso motion. The IK foot-control origin is not the ankle.
- `append_fall.py`: isolated DeadDown reference sampling, FK-to-IK matching,
  heading/ground alignment and a truly still ending.
- `overlap_recovery_collapse.py`: separate arm/body clocks and compensate targets
  with `pelvis(body_time) @ inverse(pelvis(arm_time))`. This avoids lowering the
  hand completely before the body starts collapsing.

Do not carry their old pose times or distances into a different animation.
The accepted example finishes the pass near31, yields from36, kneels56, contacts
ground72 and ends84 at30fps. Those are reference-specific, not universal timing.

Do not independently interpolate world matrices for anatomically parented chest,
head or FK arm attachments: that stretched the neck. Preserve anatomical LOCAL
positions/scales while changing rotation. Snapshot world targets before moving a
parent so a common lift isn't applied twice. DeadDown is a bundled pose reference,
not proof of an exact runtime corpse pose. Ground contact remains approximate.

## Review gates

1. Preserve input hashes; check promised prefixes/tails at quarter frames,
   with0.001 rig-unit matrix tolerance.
2. Inspect full-body front/right views, plus top or hand views when relevant.
   Fit bounds across the motion; standing-width framing hides prone-body errors.
3. Reimport GLB and compare every expected deform joint's head position
   (0.001 rig-unit tolerance). Missing joints fail. This is not full skin/rotation
   or runtime parity.
4. When using the approved fixed knife grip, compare deform prop/thumb/finger
   matrices relative to the hand against saved20 FingerTest.
5. Use golden GLB channel comparisons for a no-motion-change export regression.
6. Check a requested ending hold is still, stage only on request, and wait for the
   maintainer's visible in-game judgment. Numeric scores do not decide realism.

Maintained final sources live in repository `animation/` and may be renamed
independently. The frozen approved example and golden export are in skill `assets/examples/`. Refer to
`assets/references.json` for exact roles and hashes.
