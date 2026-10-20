"""Append hand clearance, wrist recovery and lowering to a copied approved clip.

Blender --background --python-exit-code 1 --python this.py -- recipe.json
No template edits, no reference overwrites, no gameplay or collapse changes.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/blender"))
import build_animation as builder
from motion_curves import curves, matrix_error, sample
from motion_curves import describe, smooth_monotone


def frame_set(frame):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()


def freeze_and_trim(fc, end):
    """Save existing Bezier geometry before removing the old end hold."""
    saved = [
        (k.co.x, k.handle_left.copy(), k.handle_right.copy(), k.interpolation)
        for k in fc.keyframe_points
        if k.co.x <= end
    ]
    for frame, left, right, interpolation in saved:
        k = next(k for k in fc.keyframe_points if k.co.x == frame)
        k.handle_left_type = k.handle_right_type = "FREE"
        k.handle_left, k.handle_right = left, right
    for index in range(len(fc.keyframe_points) - 1, -1, -1):
        if fc.keyframe_points[index].co.x > end:
            fc.keyframe_points.remove(fc.keyframe_points[index], fast=True)
    fc.update()
    return saved


def restore_prefix(fc, saved, end):
    """The boundary's outgoing handle may change; its incoming handle may not."""
    for frame, left, right, interpolation in saved:
        k = next(k for k in fc.keyframe_points if k.co.x == frame)
        k.handle_left_type = k.handle_right_type = "FREE"
        k.handle_left = left
        if frame < end:
            k.handle_right = right
            k.interpolation = interpolation
    fc.update()


def main():
    recipe_path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    spec = json.loads(recipe_path.read_text(encoding="utf-8"))
    source = (recipe_path.parent / spec["source_blend"]).resolve()
    assert source.name != builder.TEMPLATE_NAME
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    output = builder.BUILD_ROOT / spec["name"]
    output.mkdir(parents=True, exist_ok=True)
    target = output / (spec["name"] + ".blend")
    assert not target.exists() or (
        not (output / "validation.json").exists()
        and hashlib.sha256(target.read_bytes()).hexdigest() == source_hash
    ), "Output exists; choose a NEW name to protect reviewed edits."
    shutil.copy2(source, target)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    rig = builder.find_rig()
    scene = bpy.context.scene
    action = rig.animation_data.action
    action.name = spec["name"]
    boundary = spec["preserve_through"]
    end = spec["frame_end"]
    protected_frames = [i / 4 for i in range(boundary * 4 + 1)]
    original = sample(rig, protected_frames)
    frame_set(spec["rest_reference_frame"])
    hand = rig.pose.bones["CTRL-ArmIK.R"]
    pole = rig.pose.bones["CTRL-ElbowTarget.R"]
    rest_hand, rest_pole = hand.matrix.copy(), pole.matrix.copy()
    rest_hand.translation += Vector(spec["rest_hand_offset"])
    rest_pole.translation += Vector(spec["rest_elbow_offset"])
    frame_set(boundary)
    start_hand, start_pole = hand.matrix.copy(), pole.matrix.copy()
    original_hand_quaternion = hand.rotation_quaternion.normalized()
    # A neutral pose from frame 0 is evaluated under a different chest pose.
    # Leave reach margin under the held end-of-pass shoulder position.
    shoulder = rig.pose.bones["IK-UpperArm.R"].head.copy()
    reach_margin = (
        rig.data.bones["IK-UpperArm.R"].length + rig.data.bones["IK-Forearm.R"].length - 0.75
    )
    offset = rest_hand.translation - shoulder
    if offset.length > reach_margin:
        rest_hand.translation = shoulder + offset.normalized() * reach_margin
    clear_hand, clear_pole = start_hand.copy(), start_pole.copy()
    clear_hand.translation += Vector(spec["clear_hand_offset"])
    clear_pole.translation += Vector(spec["clear_elbow_offset"])
    relaxed_hand = clear_hand.lerp(rest_hand, spec["relax_rotation_fraction"])
    relaxed_hand.translation = clear_hand.translation.lerp(
        rest_hand.translation, spec["relax_position_fraction"]
    )
    relaxed_pole = clear_pole.lerp(rest_pole, spec["relax_position_fraction"])
    poses = [
        (spec["clear_frame"], clear_hand, clear_pole),
        (spec["relax_frame"], relaxed_hand, relaxed_pole),
        (spec["lower_frame"], rest_hand, rest_pole),
        (end, rest_hand, rest_pole),
    ]
    edited_paths = {
        hand.path_from_id("location"),
        hand.path_from_id("rotation_quaternion"),
        pole.path_from_id("location"),
    }
    saved = {
        (fc.data_path, fc.array_index): freeze_and_trim(fc, boundary)
        for fc in curves(action)
        if fc.data_path in edited_paths
    }
    for frame, hand_matrix, pole_matrix in poses:
        frame_set(frame)
        hand.matrix, pole.matrix = hand_matrix, pole_matrix
        bpy.context.view_layer.update()
        for bone in (hand, pole):
            bone.keyframe_insert("location", frame=frame, group=bone.name)
        hand.keyframe_insert("rotation_quaternion", frame=frame, group=hand.name)
    edited = [fc for fc in curves(action) if fc.data_path in edited_paths]
    qcurves = sorted(
        [fc for fc in edited if fc.data_path == hand.path_from_id("rotation_quaternion")],
        key=lambda fc: fc.array_index,
    )
    previous = list(original_hand_quaternion)
    for frame, _, _ in poses:
        points = [next(k for k in fc.keyframe_points if k.co.x == frame) for fc in qcurves]
        if sum(a * k.co.y for a, k in zip(previous, points)) < 0:
            for k in points:
                k.co.y *= -1
        previous = [k.co.y for k in points]
    for fc in edited:
        smooth_monotone(fc)
        restore_prefix(fc, saved[(fc.data_path, fc.array_index)], boundary)
    # The knife must move clear BEFORE unwinding. Keep the hand orientation
    # identical through the clearance interval, not merely at its endpoints.
    for fc in qcurves:
        k = next(k for k in fc.keyframe_points if k.co.x == boundary)
        k.interpolation = "CONSTANT"
    actual = sample(rig, protected_frames)
    maximum_error = max(
        matrix_error(a[name], b[name]) for a, b in zip(original, actual) for name in a
    )
    assert maximum_error < 0.0001, ("Approved prefix changed", maximum_error)
    # Static prop/thumb/finger curves are untouched. Assert relative transforms
    # across the complete clip, including the new recovery.
    grip_reference = None
    grip_error = 0.0
    for frame in range(0, end + 1):
        frame_set(frame)
        inverse = rig.pose.bones["Bip01_R_Hand"].matrix.inverted()
        grip = {
            name: (inverse @ rig.pose.bones[name].matrix).copy()
            for name in ("Bip01_Prop1", "Bip01_R_Finger0", "Bip01_R_Finger1")
        }
        if grip_reference is None:
            grip_reference = grip
        grip_error = max(grip_error, max(matrix_error(grip_reference[n], grip[n]) for n in grip))
    assert grip_error < 0.0001, ("Grip drifted", grip_error)
    scene.frame_end = end
    validation_spec = {
        "frame_start": 0,
        "frame_end": end,
        "validate_every_frame": True,
        "tracks": [{"bone": hand.name, "keyframes": [{"frame": 0, "location_offset": [0, 0, 0]}]}],
    }
    reach = builder.validate_right_arm_reach(rig, validation_spec)
    labels = {
        boundary: "APPROVED_PASS_END",
        spec["clear_frame"]: "KNIFE_CLEAR",
        spec["relax_frame"]: "WRIST_RELAXING",
        spec["lower_frame"]: "ARM_LOWERED",
        end: "HOLD",
    }
    for marker in list(scene.timeline_markers):
        if marker.frame > boundary:
            scene.timeline_markers.remove(marker)
    for frame, label in labels.items():
        scene.timeline_markers.new(label, frame=frame)
    diagnostics = describe(
        rig, [boundary, 60, spec["clear_frame"], 70, spec["relax_frame"], spec["lower_frame"], end]
    )
    previews = builder.render_body_previews(
        rig,
        {
            "frame_start": 0,
            "body_preview": {
                "views": ["front", "right", "front_hand", "right_hand"],
                "frames": [
                    {"frame": f, "name": labels.get(f, "MID_TRANSITION")}
                    for f in [
                        boundary,
                        60,
                        spec["clear_frame"],
                        70,
                        spec["relax_frame"],
                        spec["lower_frame"],
                    ]
                ],
            },
        },
        output,
    )
    frame_set(spec["relax_frame"])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.preferences.filepaths.file_preview_type = "NONE"
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    builder.export_glb(rig, action, output)
    report = builder.validate_glb(output / (spec["name"] + ".glb"), spec["name"])
    report.update(
        {
            "source": str(source),
            "source_sha256": source_hash,
            "preserved_through": boundary,
            "preservation_samples": len(protected_frames),
            "maximum_preservation_matrix_error": maximum_error,
            "maximum_grip_matrix_error": grip_error,
            "right_arm_reach": reach,
            "diagnostics": diagnostics,
            "previews": previews,
            "in_game_verified": False,
        }
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "RECOVERY_OK",
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"right_arm_reach", "diagnostics", "previews"}
            }
        ),
    )


if __name__ == "__main__":
    raise RuntimeError(
        "Construction reference only. Adapt to the new motion; do not replay historical frame assumptions."
    )
