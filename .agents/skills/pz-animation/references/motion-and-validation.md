# Motion editing and validation

All shared math is in `scripts/blender/motion_curves.py`, with synthetic Blender
tests in `../tests/test_retime_animation.py`. No production module imports a one-off
animation builder.

## Choosing an example

Examples are grouped by animation, with numbering restarting at `01` in each
folder. Read only the guide relevant to the requested motion:

- [Short-blade one-hand](examples/short-blade-one-hand.md): grip, wrist placement,
  manual timing, handle repair and overlapping recovery/forward collapse.
- [Head stab](examples/head-stab.md): corrected lift, repeating a hand/elbow
  stroke and adapting the native backward death motion to a full-body fall.

The numbered files are curated learning milestones, not a complete draft archive
or a build chain. File names, Blender actions, exported clips and runtime XML
identifiers are distinct. The registry records frozen binary hashes and purposes.

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

## Full-body construction

Each example's `construction/` folder contains reference-only code to inspect
and adapt. Its direct-launch guards reject historical recipe replay. Shared
curve operations live in `scripts/blender/motion_curves.py`; production tools
must not depend on these animation-specific builders.

Keep anatomical local positions and scales while changing rotations. Snapshot
world targets before moving their parent, and inspect active IK switches and
constraints before choosing controls. The example guides describe the observed
rig limitations; numeric checks do not establish contact quality.

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
