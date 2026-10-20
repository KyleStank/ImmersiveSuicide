"""Verify a generated grip against a maintainer's saved pose, read-only.

Blender --background --python this_file -- reference.blend candidate.blend
"""

import json
import sys
from pathlib import Path

import bpy


def load_copy(path):
    path = Path(path).resolve()
    if path.name == "PZ_HumanRigV4.blend":
        raise RuntimeError("Refusing to open the immutable template.")
    bpy.ops.wm.open_mainfile(filepath=str(path))
    return next(
        obj
        for obj in bpy.data.objects
        if obj.type == "ARMATURE" and obj.name.startswith("OBJ-HumanRig")
    )


def relative_grip(rig):
    bpy.context.view_layer.update()
    hand_inverse = rig.pose.bones["Bip01_R_Hand"].matrix.inverted()
    return {
        name: (hand_inverse @ rig.pose.bones[name].matrix).copy()
        for name in ("Bip01_Prop1", "Bip01_R_Finger0", "Bip01_R_Finger1")
    }


def error(a, b):
    return max(abs(a[row][col] - b[row][col]) for row in range(4) for col in range(4))


reference_path, candidate_path = sys.argv[sys.argv.index("--") + 1 :]
rig = load_copy(reference_path)
reference_frame = bpy.context.scene.frame_current
assert reference_frame == 20, "Expected the maintainer's saved pose at frame 20"
reference = relative_grip(rig)

rig = load_copy(candidate_path)
scene = bpy.context.scene
errors = []
for frame in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(frame)
    actual = relative_grip(rig)
    errors.append(max(error(reference[name], actual[name]) for name in reference))
maximum = max(errors)
assert maximum < 0.0001, ("Hand-relative grip changed", maximum)
curves = [
    fc
    for layer in rig.animation_data.action.layers
    for strip in layer.strips
    for cb in strip.channelbags
    for fc in cb.fcurves
    if "CTRL-Prop.R" in fc.data_path
]
assert len(curves) == 7 and all(len(fc.keyframe_points) == 2 for fc in curves)
print(
    json.dumps(
        {
            "matches_saved_reference": True,
            "reference_frame": reference_frame,
            "frames_checked": len(errors),
            "maximum_hand_relative_matrix_error": maximum,
            "verified_bones": list(reference),
            "prop_endpoint_key_count_per_curve": 2,
        },
        indent=2,
    )
)
