"""Read-only GLB round-trip check against a working blend's deform joint positions.

Blender --background --python-exit-code 1 --python this.py -- working.blend clip.glb
Never saves either file. A Blender round trip is not proof of game playback parity.
"""

import json
import sys
from pathlib import Path

import bpy

blend, glb = [Path(p).resolve() for p in sys.argv[sys.argv.index("--") + 1 :]]
assert blend.name != "PZ_HumanRigV4.blend"
bpy.ops.wm.open_mainfile(filepath=str(blend))
rig = next(
    o for o in bpy.data.objects if o.type == "ARMATURE" and o.name.startswith("OBJ-HumanRig")
)
scene = bpy.context.scene
frames = list(range(scene.frame_start, scene.frame_end + 1))
names = [b.name for b in rig.data.bones if b.use_deform]
expected = {}
for frame in frames:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    expected[frame] = {n: (rig.matrix_world @ rig.pose.bones[n].head).copy() for n in names}
original_objects = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(glb))
imported = [o for o in bpy.data.objects if o not in original_objects and o.type == "ARMATURE"]
assert len(imported) == 1, [o.name for o in imported]
other = imported[0]
missing = [n for n in names if n not in other.pose.bones]
if missing:
    raise RuntimeError("Export lost deform joints: " + ", ".join(missing))
assert "Bip01_L_Hand" in names and "Bip01_R_Hand" in names
errors = {n: 0.0 for n in names}
for frame in frames:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    for name in names:
        actual = other.matrix_world @ other.pose.bones[name].head
        errors[name] = max(errors[name], (actual - expected[frame][name]).length)
report = {
    "frames_checked": len(frames),
    "joint_count": len(names),
    "maximum_world_position_error": max(errors.values()),
    "per_joint": errors,
    "in_game_verified": False,
}
print("EXPORT_POSITION_CHECK", json.dumps(report))
assert max(errors.values()) < 0.001, "Export joint positions differ from Blender preview"
