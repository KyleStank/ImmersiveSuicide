"""Layer original arm recovery onto an earlier body descent, using sparse keys.

Blender --background --python-exit-code 1 --python this.py -- recipe.json
Accepted pass and later kneel/fall motion are preserved; no source overwrites.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/blender"))
import build_animation as builder
from motion_curves import curves, sample, matrix_error
from motion_curves import affine_map, retime_curve
from motion_curves import snapshot
from motion_curves import smooth_monotone
from motion_curves import frame_set


def set_frame(t):
    bpy.context.scene.frame_set(int(t), subframe=t % 1)
    bpy.context.view_layer.update()


def insert_point(fc, data):
    k = fc.keyframe_points.insert(*data["co"], options={"FAST"})
    k.handle_left_type = k.handle_right_type = "FREE"
    k.handle_left, k.handle_right = data["left"], data["right"]
    k.interpolation = data["mode"]


def main():
    path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    source = (path.parent / spec["source_blend"]).resolve()
    assert source.name != builder.TEMPLATE_NAME
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    output = builder.BUILD_ROOT / spec["name"]
    output.mkdir(parents=True, exist_ok=True)
    target = output / (spec["name"] + ".blend")
    assert not target.exists() or (
        not (output / "validation.json").exists()
        and hashlib.sha256(target.read_bytes()).hexdigest() == digest
    ), "Protected output exists; choose a NEW name."
    shutil.copy2(source, target)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    rig = builder.find_rig()
    action = rig.animation_data.action
    action.name = spec["name"]
    scene = bpy.context.scene
    boundary, join, end = spec["preserve_through"], spec["join_frame"], spec["frame_end"]
    body_map = affine_map(spec["body_time_map"])
    body_clock = affine_map([(b, a) for a, b in spec["body_time_map"]])
    arm_clock = affine_map(spec["arm_new_to_source"])
    hand, pole = rig.pose.bones["CTRL-ArmIK.R"], rig.pose.bones["CTRL-ElbowTarget.R"]
    paths = {
        hand.path_from_id("location"),
        hand.path_from_id("rotation_quaternion"),
        pole.path_from_id("location"),
    }
    original_curves = {
        (fc.data_path, fc.array_index): snapshot(fc)
        for fc in curves(action)
        if fc.data_path in paths
    }
    protected_frames = [i / 4 for i in range(boundary * 4 + 1)]
    prefix = sample(rig, protected_frames)
    # Record both source clocks before changing any curves. The relative arm
    # motion is carried by the NEW pelvis rather than left pinned in space.
    targets = {}
    for new_time in spec["arm_overlap_keys"]:
        a, b = arm_clock(new_time), body_clock(new_time)
        set_frame(a)
        old_pelvis = rig.pose.bones["CTRL-Pelvis"].matrix.copy()
        h, p = hand.matrix.copy(), pole.matrix.copy()
        set_frame(b)
        delta = rig.pose.bones["CTRL-Pelvis"].matrix @ old_pelvis.inverted()
        targets[new_time] = (delta @ h, delta @ p)
    original_key_times = [
        k.co.x
        for fc in curves(action)
        if fc.data_path == hand.path_from_id("rotation_quaternion") and fc.array_index == 0
        for k in fc.keyframe_points
    ]
    marker_data = json.loads(
        (path.parent / spec["source_metadata"]).resolve().read_text(encoding="utf-8")
    )["markers"]
    assert all(
        min(abs(t - m["exact_frame"]) for t in original_key_times) < 0.001 for m in marker_data
    ), "Stale phase metadata"
    # Body curves retain the accepted spatial trajectory; only their clock moves.
    added_retime = sum(retime_curve(fc, spec["body_time_map"]) for fc in curves(action))
    tail_times = [join + i / 4 for i in range((end - join) * 4 + 1)]
    accepted_tail = sample(rig, tail_times)
    tail_curves = {
        (fc.data_path, fc.array_index): [k for k in snapshot(fc) if k["co"][0] >= join]
        for fc in curves(action)
        if fc.data_path in paths
    }
    # Merge original pass/clearance, a newly authored overlap, and exact accepted
    # fall tail. No new per-frame keys: just four intermediate overlap poses.
    for fc in curves(action):
        key = (fc.data_path, fc.array_index)
        if key not in original_curves:
            continue
        fc.keyframe_points.clear()
        for data in original_curves[key]:
            if data["co"][0] <= boundary:
                insert_point(fc, data)
        for data in tail_curves[key]:
            insert_point(fc, data)
        fc.update()
    set_frame(boundary)
    previous_q = hand.rotation_quaternion.copy()
    for t in spec["arm_overlap_keys"]:
        set_frame(t)
        h, p = targets[t]
        hand_scale, pole_scale, pole_q = (
            hand.scale.copy(),
            pole.scale.copy(),
            pole.rotation_quaternion.copy(),
        )
        hand.matrix = h
        pole.matrix = p
        hand.scale, pole.scale, pole.rotation_quaternion = hand_scale, pole_scale, pole_q
        if previous_q.dot(hand.rotation_quaternion) < 0:
            hand.rotation_quaternion.negate()
        previous_q = hand.rotation_quaternion.copy()
        hand.keyframe_insert("location", frame=t, group=hand.name)
        hand.keyframe_insert("rotation_quaternion", frame=t, group=hand.name)
        pole.keyframe_insert("location", frame=t, group=pole.name)
    set_frame(join)
    assert (
        previous_q.dot(hand.rotation_quaternion) > 0
    ), "Quaternion hemisphere mismatch at accepted tail"
    for fc in curves(action):
        key = (fc.data_path, fc.array_index)
        if key not in original_curves:
            continue
        smooth_monotone(fc)
        # Restore accepted interval geometry, permitting only the outgoing
        # clearance handle and incoming join handle to shape the new overlap.
        for data in original_curves[key]:
            x = data["co"][0]
            if x > boundary:
                continue
            k = next(k for k in fc.keyframe_points if k.co.x == x)
            k.handle_left_type = k.handle_right_type = "FREE"
            k.handle_left = data["left"]
            if x < boundary:
                k.handle_right = data["right"]
                k.interpolation = data["mode"]
        for data in tail_curves[key]:
            x = data["co"][0]
            k = next(k for k in fc.keyframe_points if k.co.x == x)
            k.handle_left_type = k.handle_right_type = "FREE"
            k.handle_right = data["right"]
            k.interpolation = data["mode"]
            if x > join:
                k.handle_left = data["left"]
        fc.update()
    after_prefix = sample(rig, protected_frames)
    prefix_error = max(matrix_error(a[n], b[n]) for a, b in zip(prefix, after_prefix) for n in a)
    after_tail = sample(rig, tail_times)
    tail_error = max(matrix_error(a[n], b[n]) for a, b in zip(accepted_tail, after_tail) for n in a)
    assert prefix_error < 0.001, ("Pass/clearance changed", prefix_error)
    assert tail_error < 0.001, ("Accepted kneel/fall tail changed", tail_error)
    scene.frame_start, scene.frame_end = 0, end
    action.use_frame_range = False
    if scene.use_preview_range:
        scene.frame_preview_start = 0
        scene.frame_preview_end = end
    arm_labels = {
        "START",
        "LIFT",
        "PREPARE_WRIST",
        "APPROACH",
        "BLADE_SETUP",
        "PASS_END",
        "KNIFE_CLEAR",
        "WRIST_RELAXING",
        "ARM_LOWERED",
    }
    arm_to_new = affine_map([(b, a) for a, b in spec["arm_new_to_source"]])
    new_markers = []
    for m in marker_data:
        t = arm_to_new(m["exact_frame"]) if m["name"] in arm_labels else body_map(m["exact_frame"])
        new_markers.append({"name": m["name"], "exact_frame": t, "ui_frame": round(t)})
    new_markers.append({"name": "BODY_YIELD_START", "exact_frame": boundary, "ui_frame": boundary})
    for marker in list(scene.timeline_markers):
        scene.timeline_markers.remove(marker)
    for m in new_markers:
        scene.timeline_markers.new(m["name"], frame=m["ui_frame"])
    reach = builder.validate_right_arm_reach(
        rig,
        {
            "frame_start": 0,
            "frame_end": end,
            "validate_every_frame": True,
            "tracks": [
                {"bone": hand.name, "keyframes": [{"frame": 0, "location_offset": [0, 0, 0]}]}
            ],
        },
    )
    diagnostics = []
    for frame in [31, 36, 38, 41, 44, 49, 52, 56, 72, 84]:
        frame_set(frame)
        diagnostics.append(
            {
                "frame": frame,
                "pelvis": list(rig.pose.bones["CTRL-Pelvis"].head),
                "hand": list(rig.pose.bones["Bip01_R_Hand"].head),
            }
        )
    hold = sample(rig, list(range(72, end + 1)))
    hold_error = max(matrix_error(hold[0][n], p[n]) for p in hold for n in p)
    assert hold_error < 0.0001, ("Final pose moves", hold_error)
    previews = builder.render_body_previews(
        rig,
        {
            "frame_start": 0,
            "body_preview": {
                "views": ["front", "right"],
                "frames": [
                    {"frame": f, "name": "OVERLAP"} for f in [36, 38, 41, 44, 49, 52, 56, 72]
                ],
            },
        },
        output,
    )
    frame_set(41)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.preferences.filepaths.file_preview_type = "NONE"
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    builder.export_glb(rig, action, output)
    report = builder.validate_glb(output / (spec["name"] + ".glb"), spec["name"])
    report.update(
        {
            "source": str(source),
            "source_sha256": digest,
            "fps": 30,
            "duration_seconds": end / 30,
            "body_time_map": spec["body_time_map"],
            "arm_new_to_source": spec["arm_new_to_source"],
            "preserved_through": boundary,
            "prefix_samples": len(protected_frames),
            "maximum_prefix_matrix_error": prefix_error,
            "accepted_tail_from": join,
            "tail_samples": len(tail_times),
            "maximum_tail_matrix_error": tail_error,
            "retime_helper_scalar_keys_added": added_retime,
            "new_overlap_pose_times": spec["arm_overlap_keys"],
            "markers": new_markers,
            "diagnostics": diagnostics,
            "final_hold_matrix_error": hold_error,
            "right_arm_reach": reach,
            "previews": previews,
            "in_game_verified": False,
        }
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "OVERLAP_OK",
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"markers", "diagnostics", "previews", "right_arm_reach"}
            }
        ),
    )


if __name__ == "__main__":
    raise RuntimeError(
        "Construction reference only. Adapt to the new motion; do not replay historical frame assumptions."
    )
