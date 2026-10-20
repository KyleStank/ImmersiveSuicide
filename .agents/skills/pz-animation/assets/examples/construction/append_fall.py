"""Append a forward fall using the rig's DeadDown pose as a prone reference.

Blender --background --python-exit-code 1 --python this.py -- recipe.json
Copies approved source; never opens template or overwrites reviewed outputs.
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
from motion_curves import curves, sample, matrix_error
from motion_curves import smooth_monotone
from motion_curves import freeze_and_trim, restore_prefix, frame_set
from append_kneel import mesh_points


def pole_from_joint(hip, knee, ankle):
    axis = ankle - hip
    projected = hip + axis * (knee - hip).dot(axis) / axis.length_squared
    bend = knee - projected
    return knee + bend.normalized() * 15 if bend.length > 0.01 else knee + Vector((0, 0, 15))


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
    boundary, end = spec["preserve_through"], spec["frame_end"]
    frame_set(boundary)
    foot_relative = {
        s: rig.pose.bones["CTRL-LegIK." + s].matrix.inverted()
        @ rig.pose.bones["Bip01_" + s + "_Foot"].matrix
        for s in ("R", "L")
    }
    # Evaluate reference in isolation; reload the working copy afterwards so
    # its extra action channels, IK switches or bbone settings cannot leak back.
    ref_action = bpy.data.actions[spec["reference_action"]]
    rig.animation_data.action = ref_action
    rig.animation_data.action_slot = ref_action.slots[0]
    for prop in ("arm_ik_r", "arm_ik_l", "leg_ik_r", "leg_ik_l"):
        setattr(rig.pz_human_props, prop, 0.0)
    rig.update_tag()
    frame_set(int(ref_action.frame_range[0]))
    builder.snap_right_arm_ik_to_current_fk(rig)
    names = [
        "CTRL-Pelvis",
        "CTRL-Chest",
        "CTRL-Head",
        "CTRL-ArmIK.R",
        "CTRL-ElbowTarget.R",
        "CTRL-LegIK.R",
        "CTRL-LegIK.L",
        "CTRL-KneeTarget.R",
        "CTRL-KneeTarget.L",
        "CTRL-UpperArmFK.L",
        "CTRL-ForearmFK.L",
        "CTRL-HandFK.L",
    ]
    reference = {n: rig.pose.bones[n].matrix.copy() for n in names}
    reference_local = {
        n: {"location": rig.pose.bones[n].location.copy(), "scale": rig.pose.bones[n].scale.copy()}
        for n in names
    }
    for side in ("R", "L"):
        reference["CTRL-LegIK." + side] = (
            rig.pose.bones["Bip01_" + side + "_Foot"].matrix @ foot_relative[side].inverted()
        )
        hip, knee, ankle = [
            rig.pose.bones["Bip01_" + side + "_" + n].head.copy() for n in ("Thigh", "Calf", "Foot")
        ]
        reference["CTRL-KneeTarget." + side].translation = pole_from_joint(hip, knee, ankle)
    ref_body = next(o for o in bpy.data.objects if o.name.startswith("OBJ-MaleBody"))
    ref_floor = min(p.z for p in mesh_points(ref_body, rig))
    ref_forward = reference["CTRL-Pelvis"].to_3x3().col[1].normalized()
    yaw = -math.atan2(ref_forward.x, -ref_forward.y)
    heading = Quaternion((0, 0, 1), yaw).to_matrix().to_4x4()
    ref_pelvis_position = heading @ reference["CTRL-Pelvis"].translation

    bpy.ops.wm.open_mainfile(filepath=str(target))
    rig = builder.find_rig()
    scene = bpy.context.scene
    action = rig.animation_data.action
    action.name = spec["name"]
    protected_frames = [i / 4 for i in range(boundary * 4 + 1)]
    original = sample(rig, protected_frames)
    frame_set(boundary)
    base = {n: rig.pose.bones[n].matrix.copy() for n in names}
    controlled = {n: ("location", "rotation_quaternion", "scale") for n in names}
    local = {
        n: {p: tuple(getattr(rig.pose.bones[n], p)) for p in props}
        for n, props in controlled.items()
    }
    body = next(o for o in bpy.data.objects if o.name.startswith("OBJ-MaleBody"))
    floor = min(p.z for p in mesh_points(body, rig))
    knee_pivot = (rig.pose.bones["Bip01_R_Calf"].head + rig.pose.bones["Bip01_L_Calf"].head) * 0.5
    target_hip = Vector(
        (
            base["CTRL-Pelvis"].translation.x,
            knee_pivot.y - rig.data.bones["IK-Thigh.R"].length,
            ref_pelvis_position.z + floor - ref_floor + 0.25,
        )
    )
    alignment = Matrix.Translation(target_hip - ref_pelvis_position) @ heading
    final = {n: alignment @ m for n, m in reference.items()}
    (output / "prone-reference.json").write_text(
        json.dumps(
            {
                "action": spec["reference_action"],
                "reference_heading_correction_degrees": math.degrees(yaw),
                "ground_z": floor,
                "target_hip": list(target_hip),
                "control_matrices": {n: [list(row) for row in m] for n, m in final.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Group indices for approximate skin contact checks/corrections.
    foot_indices = {}
    for s in ("R", "L"):
        index = body.vertex_groups["Bip01_" + s + "_Foot"].index
        foot_indices[s] = [
            v.index
            for v in body.data.vertices
            if any(g.group == index and g.weight > 0.35 for g in v.groups)
        ]
    torso_groups = {
        g.index
        for g in body.vertex_groups
        if any(token in g.name for token in ("Pelvis", "Spine", "Neck", "Head"))
    }
    torso_indices = [
        v.index
        for v in body.data.vertices
        if sum(g.weight for g in v.groups if g.group in torso_groups) > 0.5
    ]
    paths = {rig.pose.bones[n].path_from_id(p) for n, props in controlled.items() for p in props}
    saved = {
        (fc.data_path, fc.array_index): freeze_and_trim(fc, boundary)
        for fc in curves(action)
        if fc.data_path in paths
    }
    for n, props in controlled.items():
        b = rig.pose.bones[n]
        for p in props:
            setattr(b, p, local[n][p])
            b.keyframe_insert(p, frame=boundary, group=n)
            if not any(k[0] == b.path_from_id(p) for k in saved):
                b.keyframe_insert(p, frame=0, group=n)
    previous = {n: rig.pose.bones[n].rotation_quaternion.copy() for n in names}
    for pose in spec["poses"]:
        frame_set(pose["frame"])
        rotation = Quaternion((1, 0, 0), math.radians(pose["pitch"])).to_matrix().to_4x4()
        hinge = Matrix.Translation(knee_pivot) @ rotation @ Matrix.Translation(-knee_pivot)
        for n in names:
            if "LegIK" in n or "KneeTarget" in n:
                matrix = base[n].lerp(final[n], pose["legs_blend"])
            else:
                matrix = (hinge @ base[n]).lerp(final[n], pose["reference_blend"])
            rig.pose.bones[n].matrix = matrix
            if n in (
                "CTRL-Chest",
                "CTRL-Head",
                "CTRL-UpperArmFK.L",
                "CTRL-ForearmFK.L",
                "CTRL-HandFK.L",
            ):
                # These are anatomical attachments, not independent world-space
                # targets. A matrix lerp otherwise stretches neck/shoulder joints.
                attachment_blend = min(1.0, (pose["frame"] - boundary) / 20.0)
                rig.pose.bones[n].location = Vector(local[n]["location"]).lerp(
                    reference_local[n]["location"], attachment_blend
                )
                rig.pose.bones[n].scale = Vector(local[n]["scale"]).lerp(
                    reference_local[n]["scale"], attachment_blend
                )
            bpy.context.view_layer.update()
        # Keep feet close to the ground while they unroll. Whole-body support
        # is approximate; do not vertically drag the fixed CTRL-Root.
        for iteration in range(2):
            points = mesh_points(body, rig)
            for s in ("R", "L"):
                minimum = min(points[i].z for i in foot_indices[s])
                foot = rig.pose.bones["CTRL-LegIK." + s]
                m = foot.matrix.copy()
                m.translation.z += floor - minimum
                foot.matrix = m
            bpy.context.view_layer.update()
        points = mesh_points(body, rig)
        penetration = floor - min(points[i].z for i in torso_indices)
        if penetration > 0:
            # Apply the same lift to all torso/arm targets, not just the pelvis.
            lift = Matrix.Translation((0, 0, penetration + 0.1))
            lifted = {
                n: lift @ rig.pose.bones[n].matrix.copy()
                for n in names
                if "LegIK" not in n and "KneeTarget" not in n
            }
            for n, m in lifted.items():
                rig.pose.bones[n].matrix = m
                bpy.context.view_layer.update()
        for n, props in controlled.items():
            b = rig.pose.bones[n]
            if previous[n].dot(b.rotation_quaternion) < 0:
                b.rotation_quaternion.negate()
            previous[n] = b.rotation_quaternion.copy()
            for p in props:
                b.keyframe_insert(p, frame=pose["frame"], group=n)
    for fc in curves(action):
        if fc.data_path in paths:
            smooth_monotone(fc)
            frozen = saved.get((fc.data_path, fc.array_index))
            if frozen:
                restore_prefix(fc, frozen, boundary)
    actual = sample(rig, protected_frames)
    error = max(matrix_error(a[n], b[n]) for a, b in zip(original, actual) for n in a)
    assert error < 0.0001, ("Approved prefix changed", error)
    scene.frame_end = end
    arm_reach = builder.validate_right_arm_reach(
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
    diagnostics = []
    settled = None
    still_error = 0
    for frame in range(boundary, end + 1):
        frame_set(frame)
        for side in ("R", "L"):
            limit = (
                rig.data.bones["IK-Thigh." + side].length
                + rig.data.bones["IK-Calf." + side].length
                + 0.5
            )
            distance = (
                rig.pose.bones["CTRL-LegIK." + side].head - rig.pose.bones["IK-Thigh." + side].head
            ).length
            assert distance <= limit, ("Fall leg target too far", frame, side, distance, limit)
        points = mesh_points(body, rig)
        diagnostics.append(
            {
                "frame": frame,
                "skin_minimum_z": min(p.z for p in points),
                "torso_minimum_z": min(points[i].z for i in torso_indices),
                "hips": list(rig.pose.bones["CTRL-Pelvis"].head),
            }
        )
        if frame >= 194:
            pose = {b.name: b.matrix.copy() for b in rig.pose.bones}
            if settled is None:
                settled = pose
            still_error = max(still_error, max(matrix_error(settled[n], pose[n]) for n in pose))
    assert still_error < 0.0001, ("Final pose moves", still_error)
    for marker in list(scene.timeline_markers):
        if marker.frame > boundary:
            scene.timeline_markers.remove(marker)
    for p in spec["poses"]:
        scene.timeline_markers.new(p["label"], frame=p["frame"])
    previews = builder.render_body_previews(
        rig,
        {
            "frame_start": 0,
            "body_preview": {
                "views": ["right", "top"],
                "frames": [
                    {"frame": f, "name": "FALL_REVIEW"} for f in [150, 158, 170, 176, 180, 186, 194]
                ],
            },
        },
        output,
    )
    frame_set(194)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.preferences.filepaths.file_preview_type = "NONE"
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    builder.export_glb(rig, action, output)
    report = builder.validate_glb(output / (spec["name"] + ".glb"), spec["name"])
    report.update(
        {
            "source": str(source),
            "source_sha256": digest,
            "reference_action": spec["reference_action"],
            "preserved_through": boundary,
            "preservation_samples": len(protected_frames),
            "maximum_preservation_matrix_error": error,
            "ground_z": floor,
            "final_hold_matrix_error": still_error,
            "contact_samples": diagnostics,
            "right_arm_reach": arm_reach,
            "previews": previews,
            "in_game_verified": False,
        }
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "FALL_OK",
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"previews", "contact_samples", "right_arm_reach"}
            }
        ),
    )


if __name__ == "__main__":
    raise RuntimeError(
        "Construction reference only. Adapt to the new motion; do not replay historical frame assumptions."
    )
