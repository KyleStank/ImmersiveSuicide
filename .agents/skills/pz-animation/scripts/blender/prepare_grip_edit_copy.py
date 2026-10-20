"""Save an editable, unkeyed thumb/finger reference from a generated clip.

Run Blender with the generated .blend, --python this_file -- destination.blend.
Never overwrites an existing reference, and never saves over the input file.
"""

import sys
import argparse
from pathlib import Path

import bpy

parser = argparse.ArgumentParser()
parser.add_argument("destination")
parser.add_argument("--frame", type=int)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
destination = Path(args.destination).resolve()
source = Path(bpy.data.filepath).resolve()
if source.name == "PZ_HumanRigV4.blend" or destination == source or destination.exists():
    raise RuntimeError("Requires a generated input and a NEW reference destination.")
rig = next(
    obj
    for obj in bpy.data.objects
    if obj.type == "ARMATURE" and obj.name.startswith("OBJ-HumanRig")
)
scene = bpy.context.scene
frame = scene.frame_current if args.frame is None else args.frame
if not scene.frame_start <= frame <= scene.frame_end:
    raise ValueError("Choose a frame inside the source clip")
scene.frame_set(frame)
bpy.context.view_layer.update()
names = {"CTRL-Thumb.R", "CTRL-Fingers.R"}
rotations = {name: rig.pose.bones[name].rotation_quaternion.copy() for name in names}
action = rig.animation_data.action
for layer in action.layers:
    for strip in layer.strips:
        for channelbag in strip.channelbags:
            for curve in list(channelbag.fcurves):
                if any(f'pose.bones["{name}"]' in curve.data_path for name in names):
                    channelbag.fcurves.remove(curve)
for name, rotation in rotations.items():
    rig.pose.bones[name].rotation_quaternion = rotation
scene.tool_settings.use_keyframe_insert_auto = False
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
for bone in rig.pose.bones:
    bone.select = bone.name in names
rig.data.bones.active = rig.data.bones["CTRL-Fingers.R"]
bpy.ops.object.mode_set(mode="POSE")
bpy.context.view_layer.update()
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(destination))
print("GRIP_EDIT_COPY_READY", destination)
