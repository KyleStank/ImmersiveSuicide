"""Read-only comparison of edited timing; writes a diagnostic JSON, no .blends.

Blender --background --python-exit-code 1 --python this.py -- old.blend new.blend report.json
"""

import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motion_curves import curves


def snapshot(path):
    assert Path(path).name != "PZ_HumanRigV4.blend"
    bpy.ops.wm.open_mainfile(filepath=str(Path(path).resolve()))
    rig = next(
        o for o in bpy.data.objects if o.type == "ARMATURE" and o.name.startswith("OBJ-HumanRig")
    )
    action = rig.animation_data.action
    channels = {
        (fc.data_path, fc.array_index): [
            {
                "co": list(k.co),
                "left": list(k.handle_left),
                "right": list(k.handle_right),
                "mode": k.interpolation,
            }
            for k in fc.keyframe_points
        ]
        for fc in curves(action)
    }
    frames = [i / 4 for i in range(int(action.frame_range[1]) * 4 + 1)]
    motion = []
    for frame in frames:
        bpy.context.scene.frame_set(int(frame), subframe=frame % 1)
        bpy.context.view_layer.update()
        motion.append(
            {
                "frame": frame,
                "hip": list(rig.pose.bones["CTRL-Pelvis"].head),
                "head": list(rig.pose.bones["Bip01_Head"].head),
                "hand": list(rig.pose.bones["Bip01_R_Hand"].head),
                "wrist_quaternion": list(
                    rig.pose.bones["CTRL-ArmIK.R"].rotation_quaternion.normalized()
                ),
            }
        )
    problematic = []
    for (name, index), keys in channels.items():
        for a, b in zip(keys, keys[1:]):
            span = b["co"][0] - a["co"][0]
            if a["mode"] != "BEZIER" or abs(b["co"][1] - a["co"][1]) < 0.0001:
                continue
            extent = (a["right"][0] - a["co"][0]) + (b["co"][0] - b["left"][0])
            if extent > span + 0.0001:
                problematic.append(
                    {
                        "path": name,
                        "component": index,
                        "from": a["co"][0],
                        "to": b["co"][0],
                        "handle_span_ratio": extent / span,
                    }
                )
    # Mean per-frame speeds by central finite difference, in rig units/frame.
    speeds = {}
    for integer in range(1, int(action.frame_range[1])):
        i = integer * 4
        speeds[str(integer)] = {
            name: math.sqrt(
                sum((a - b) ** 2 for a, b in zip(motion[i + 1][name], motion[i - 1][name]))
            )
            / 0.5
            for name in ("hip", "head", "hand")
        }
    return {
        "action_range": list(action.frame_range),
        "scene_range": [bpy.context.scene.frame_start, bpy.context.scene.frame_end],
        "fps": bpy.context.scene.render.fps,
        "channels": channels,
        "motion": motion,
        "speeds": speeds,
        "overlapping_handles": sorted(
            problematic, key=lambda x: x["handle_span_ratio"], reverse=True
        ),
    }


old_path, new_path, report_path = sys.argv[sys.argv.index("--") + 1 :]
old = snapshot(old_path)
new = snapshot(new_path)
pairs = []
max_value_difference = 0
different_counts = []
for channel, keys in new["channels"].items():
    previous = old["channels"].get(channel)
    if previous is None or len(previous) != len(keys):
        different_counts.append(str(channel))
        continue
    max_value_difference = max(
        max_value_difference, max(abs(a["co"][1] - b["co"][1]) for a, b in zip(previous, keys))
    )
    if channel == ('pose.bones["CTRL-ArmIK.R"].location', 0):
        pairs = [[a["co"][0], b["co"][0]] for a, b in zip(previous, keys)]
report = {
    "old_action_range": old["action_range"],
    "new_action_range": new["action_range"],
    "new_scene_range": new["scene_range"],
    "fps": new["fps"],
    "maximum_key_value_difference": max_value_difference,
    "channels_with_different_key_counts": different_counts,
    "hand_location_key_time_pairs": pairs,
    "overlapping_handles_before": len(old["overlapping_handles"]),
    "overlapping_handles_after": len(new["overlapping_handles"]),
    "worst_overlapping_handles": new["overlapping_handles"][:12],
    "speeds_at_integer_frames": new["speeds"],
}
Path(report_path).resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
print(
    "TIMING_DIAGNOSIS",
    json.dumps({k: v for k, v in report.items() if k != "speeds_at_integer_frames"}),
)
