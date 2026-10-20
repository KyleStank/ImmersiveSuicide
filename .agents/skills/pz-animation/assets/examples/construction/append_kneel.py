"""Append a sparse IK kneeling descent to a copied approved recovery clip.

Blender --background --python-exit-code 1 --python this.py -- recipe.json
No template edits or overwrite of reviewed references. Kneeling only, no fall.
"""

import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/blender"))
import build_animation as builder
from motion_curves import curves, matrix_error, sample
from motion_curves import smooth_monotone
from motion_curves import freeze_and_trim, restore_prefix, frame_set


def rotate_at_head(matrix, degrees):
    target = Quaternion((1, 0, 0), math.radians(degrees)).to_matrix().to_4x4() @ matrix
    target.translation = matrix.translation
    return target


def mesh_points(body, rig):
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    transform = rig.matrix_world.inverted() @ body.matrix_world
    points = [transform @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


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
    scene = bpy.context.scene
    action = rig.animation_data.action
    action.name = spec["name"]
    boundary, end = spec["preserve_through"], spec["frame_end"]
    protected_frames = [i / 4 for i in range(boundary * 4 + 1)]
    original = sample(rig, protected_frames)
    frame_set(boundary)
    controlled = {
        "CTRL-Pelvis": ("location", "rotation_quaternion"),
        "CTRL-Chest": ("location", "rotation_quaternion"),
        "CTRL-Head": ("location", "rotation_quaternion"),
        "CTRL-ArmIK.R": ("location", "rotation_quaternion"),
        "CTRL-ElbowTarget.R": ("location",),
        "CTRL-LegIK.R": ("location", "rotation_quaternion"),
        "CTRL-LegIK.L": ("location", "rotation_quaternion"),
        "CTRL-KneeTarget.R": ("location",),
        "CTRL-KneeTarget.L": ("location",),
    }
    # Assigning a matrix also decomposes scale, and head/chest matrices may
    # compensate parent motion with location. Key all those channels explicitly
    # so a new unkeyed value cannot leak back into the approved prefix.
    controlled = {name: props + ("scale",) for name, props in controlled.items()}
    base = {name: rig.pose.bones[name].matrix.copy() for name in controlled}
    # This rig's foot-control origin is offset from the solved ankle. Calibrate
    # the target-distance limit against the accepted standing pose, not just
    # the sum of the raw rest lengths (which would reject that pose itself).
    leg_target_limits = {
        s: max(
            rig.data.bones["IK-Thigh." + s].length + rig.data.bones["IK-Calf." + s].length + 0.5,
            (rig.pose.bones["CTRL-LegIK." + s].head - rig.pose.bones["IK-Thigh." + s].head).length
            + 0.15,
        )
        for s in ("R", "L")
    }
    locals_at_boundary = {
        name: {prop: tuple(getattr(rig.pose.bones[name], prop)) for prop in props}
        for name, props in controlled.items()
    }
    # Mesh-derived toe pivots, in armature coordinates. Root stays fixed.
    body = next(o for o in bpy.data.objects if o.name.startswith("OBJ-MaleBody"))
    indices = {}
    points = mesh_points(body, rig)
    floor = min(p.z for p in points)
    toes = {}
    for side in ("R", "L"):
        group = body.vertex_groups["Bip01_" + side + "_Foot"].index
        indices[side] = [
            v.index
            for v in body.data.vertices
            if any(g.group == group and g.weight > 0.35 for g in v.groups)
        ]
        sole = [points[i] for i in indices[side] if points[i].z < floor + 0.8]
        assert sole, "No sole vertices for " + side
        toe_y = min(v.y for v in sole)
        front = [v for v in sole if v.y < toe_y + 0.8]
        toes[side] = Vector((sum(v.x for v in front) / len(front), toe_y, floor))
    edited_paths = {
        rig.pose.bones[name].path_from_id(prop)
        for name, props in controlled.items()
        for prop in props
    }
    saved = {
        (fc.data_path, fc.array_index): freeze_and_trim(fc, boundary)
        for fc in curves(action)
        if fc.data_path in edited_paths
    }
    # Explicit boundary keys prevent a new location channel starting to move
    # before the approved interval ends. Existing curves retain their handles.
    for name, props in controlled.items():
        bone = rig.pose.bones[name]
        for prop in props:
            setattr(bone, prop, locals_at_boundary[name][prop])
            bone.keyframe_insert(prop, frame=boundary, group=name)
            if not any(key[0] == bone.path_from_id(prop) for key in saved):
                bone.keyframe_insert(prop, frame=0, group=name)
    key_contact = []
    previous_q = {name: rig.pose.bones[name].rotation_quaternion.copy() for name in controlled}
    for pose in spec["poses"]:
        frame = pose["frame"]
        frame_set(frame)
        pelvis = rotate_at_head(base["CTRL-Pelvis"], pose["pelvis_lean"])
        pelvis.translation += Vector(pose["pelvis_offset"])
        rig.pose.bones["CTRL-Pelvis"].matrix = pelvis
        bpy.context.view_layer.update()
        delta = pelvis @ base["CTRL-Pelvis"].inverted()
        for name, angle in [("CTRL-Chest", pose["chest_lean"]), ("CTRL-Head", pose["head_lean"])]:
            # World-space targets include the pelvis displacement. Head then
            # follows the additional chest lean, rather than pinning in space.
            target_matrix = delta @ base[name]
            target_matrix = rotate_at_head(target_matrix, angle)
            rig.pose.bones[name].matrix = target_matrix
            bpy.context.view_layer.update()
        for name in ("CTRL-ArmIK.R", "CTRL-ElbowTarget.R"):
            rig.pose.bones[name].matrix = delta @ base[name]
        for side in ("R", "L"):
            name = "CTRL-LegIK." + side
            toe = toes[side]
            rotation = (
                Quaternion((1, 0, 0), math.radians(pose["heel_" + side.lower()]))
                .to_matrix()
                .to_4x4()
            )
            rig.pose.bones[name].matrix = (
                Matrix.Translation(toe) @ rotation @ Matrix.Translation(-toe) @ base[name]
            )
            knee = base["CTRL-KneeTarget." + side].copy()
            knee.translation += Vector(spec["knee_pole_offset"]) * pose["pole_fraction"]
            rig.pose.bones["CTRL-KneeTarget." + side].matrix = knee
        bpy.context.view_layer.update()
        # Correct foot sole height at authored poses after the rig has solved.
        for iteration in range(2):
            actual_points = mesh_points(body, rig)
            for side in ("R", "L"):
                minimum = min(actual_points[i].z for i in indices[side])
                foot = rig.pose.bones["CTRL-LegIK." + side]
                m = foot.matrix.copy()
                m.translation.z += floor - minimum
                foot.matrix = m
            bpy.context.view_layer.update()
        key_contact.append(
            {
                "frame": frame,
                "knees": {s: list(rig.pose.bones["Bip01_" + s + "_Calf"].head) for s in ("R", "L")},
            }
        )
        for name, props in controlled.items():
            bone = rig.pose.bones[name]
            if "rotation_quaternion" in props:
                if previous_q[name].dot(bone.rotation_quaternion) < 0:
                    bone.rotation_quaternion.negate()
                previous_q[name] = bone.rotation_quaternion.copy()
            for prop in props:
                bone.keyframe_insert(prop, frame=frame, group=name)
    for fc in curves(action):
        if fc.data_path in edited_paths:
            smooth_monotone(fc)
            frozen = saved.get((fc.data_path, fc.array_index))
            if frozen:
                restore_prefix(fc, frozen, boundary)
    actual = sample(rig, protected_frames)
    preservation_error = max(matrix_error(a[n], b[n]) for a, b in zip(original, actual) for n in a)
    if preservation_error >= 0.0001:
        differences = sorted(
            [
                (matrix_error(a[n], b[n]), f, n)
                for f, a, b in zip(protected_frames, original, actual)
                for n in a
            ],
            reverse=True,
        )
        print("PREFIX_DIFFERENCES", differences[:8])
    assert preservation_error < 0.0001, ("Approved prefix changed", preservation_error)
    # Reach for BOTH legs, and toe/sole height during the entire new segment.
    contact = []
    for frame in range(boundary, end + 1):
        frame_set(frame)
        for side in ("R", "L"):
            length = (
                rig.data.bones["IK-Thigh." + side].length + rig.data.bones["IK-Calf." + side].length
            )
            distance = (
                rig.pose.bones["CTRL-LegIK." + side].head - rig.pose.bones["IK-Thigh." + side].head
            ).length
            assert distance <= leg_target_limits[side], (
                "Leg target too far",
                frame,
                side,
                distance,
                leg_target_limits[side],
            )
        points_now = mesh_points(body, rig)
        contact.append(
            {
                "frame": frame,
                "minimum_foot_z": {s: min(points_now[i].z for i in indices[s]) for s in ("R", "L")},
            }
        )
    minimum_sole = min(row["minimum_foot_z"][s] for row in contact for s in ("R", "L"))
    maximum_sole = max(row["minimum_foot_z"][s] for row in contact for s in ("R", "L"))
    assert minimum_sole >= floor - 1.0, ("Foot penetrates baseline too far", minimum_sole, floor)
    assert maximum_sole <= floor + 1.0, ("Foot loses ground contact", maximum_sole, floor)
    scene.frame_end = end
    reach = builder.validate_right_arm_reach(
        rig,
        {
            "frame_start": 0,
            "frame_end": end,
            "validate_every_frame": True,
            "tracks": [
                {"bone": "CTRL-ArmIK.R", "keyframes": [{"frame": 0, "location_offset": [0, 0, 0]}]}
            ],
        },
    )
    for marker in list(scene.timeline_markers):
        if marker.frame > boundary:
            scene.timeline_markers.remove(marker)
    for pose in spec["poses"]:
        scene.timeline_markers.new(pose["label"], frame=pose["frame"])
    previews = builder.render_body_previews(
        rig,
        {
            "frame_start": 0,
            "body_preview": {
                "views": ["front", "right"],
                "frames": [
                    {"frame": f, "name": "KNEEL_REVIEW"} for f in [96, 108, 116, 124, 132, 140, 150]
                ],
            },
        },
        output,
    )
    frame_set(150)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.preferences.filepaths.file_preview_type = "NONE"
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    builder.export_glb(rig, action, output)
    report = builder.validate_glb(output / (spec["name"] + ".glb"), spec["name"])
    report.update(
        {
            "source": str(source),
            "source_sha256": digest,
            "preserved_through": boundary,
            "preservation_samples": len(protected_frames),
            "maximum_preservation_matrix_error": preservation_error,
            "ground_z": floor,
            "toe_pivots": {s: list(v) for s, v in toes.items()},
            "calibrated_leg_target_limits": leg_target_limits,
            "maximum_sole_penetration": max(0, floor - minimum_sole),
            "maximum_sole_lift": max(0, maximum_sole - floor),
            "sole_height_tolerance_rig_units": 1.0,
            "key_knee_positions": key_contact,
            "foot_contact_samples": contact,
            "right_arm_reach": reach,
            "previews": previews,
            "in_game_verified": False,
        }
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "KNEEL_OK",
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"previews", "right_arm_reach", "foot_contact_samples"}
            }
        ),
    )


if __name__ == "__main__":
    raise RuntimeError(
        "Construction reference only. Adapt to the new motion; do not replay historical frame assumptions."
    )
