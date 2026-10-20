# Rig and authoring

## Verified conventions

Tested with Blender5.2.2 LTS. Initialize machine paths as described in workflow.md;
commands also accept an explicit `-BlenderPath`. Bundled Paddlefruit scripts execute from a COPIED rig. The original
rig is required locally but may have separate redistribution/licensing constraints.

Rig-space: up+Z, forward-Y, right-arm outward-X; model is roughly100 units tall.
Schema1 semantic offsets map up/forward/outward to these axes. Raw controller
location offsets are local and are not interchangeable with rig-space offsets.
`CTRL-ArmIK.R` and `CTRL-ElbowTarget.R` are root-parented (Root Child Of weight1,
pelvis/chest0). They do not automatically descend with the pelvis.

Select the reference action's Blender5 action SLOT before evaluating it. Sample
`Idle` as a pose, not as hundreds of copied motion curves. Geometrically initialize
right-arm IK from FK shoulder/elbow/wrist and the bend-plane pole; default pole
placement previously produced an arm crossing the body.

`build_animation.create_action` now calls `preserve_static_pose`: non-default
unanimated control components and IK switches get two identical endpoint keys.
Without them NLA/export can reset the left arm or other unkeyed controls to rest.
Static head/foot channels in the editor are not necessarily unwanted movement.
Moving tracks remain sparse (the sample gesture uses five authored poses).

## Reusable knife grip

[../assets/kitchen-knife-grip.json](../assets/kitchen-knife-grip.json) contains accepted `constant_controls`:
right prop location/quaternion, thumb and fingers quaternion. Copy that field into
a new schema1 spec, or apply it to an otherwise unanimated grip. These are local
controller transforms for V4, not global hand positions or universal weapon axes.
Reference is the saved frame20 FingerTest example. User-approved thumb clipping
is intentional. Do not change the grip to conceal an arm or wrist pose problem.

The knife preview is a real game mesh: raw coordinates `(x,y,z)` map to
`100*(x,z,y)` with reversed face winding. Parent preview via COPY_TRANSFORMS to
deform `Bip01_Prop1`, exclude preview object from GLB; game supplies held mesh.
Older backwards Blender previews were a preview-basis bug, not evidence that the
game attachment needed reversing. Optional preview mesh/texture paths must point
at a local game installation via `game:media/...`; configure its root using
`initialize.ps1 -ProjectZomboidPath`. Game assets are not bundled in the starter recipes.
For another item, inspect its actual geometry/attachment; don't assume knife axes.

## Where automation stops

Schema1 supports right-hand semantic offsets, wrist alignment, local rotations,
elbow height, fixed grip and optional prop-target poses. It is NOT a general
natural-language full-body solver. Full-body continuations still require adapting
the existing specialist builders and making reviewed pose decisions.
No generic collision solver, physics simulation or automatic realism score exists.

For an optional single-pose thumb/finger correction, `prepare_grip_edit_copy.py`
saves a NEW editable copy with those channels unkeyed at the saved frame (or an
explicit `--frame`). It never saves over the source. Inspect the user's corrected
local transforms and apply them as a reusable fixed grip; don't request per-frame
manual work. `inspect_reference_poses.py` is a read-only inspector for bundled rig
actions and should be run on a working copy, never the immutable template.
