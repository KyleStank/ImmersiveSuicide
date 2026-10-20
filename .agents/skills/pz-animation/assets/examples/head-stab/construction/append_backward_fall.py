"""Append a sparse full-body backward fall using the installed native death clip."""

import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(root / 'scripts/blender'))
from native_death_reference import NativeDeath
import build_animation as builder
import recipe
from motion_curves import curves, frame_set, freeze_and_trim, matrix_error
from motion_curves import restore_prefix, sample, smooth_monotone


def main():
    clip_name = 'Bob_IS_HeadStab_FallExample'
    source = root / 'assets/examples/head-stab/03-approved-three-stabs.blend'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    reference_path = recipe.resolve_path('game:media/anims_X/Zombie/Zombie_Death.X', root)
    reference_hash = hashlib.sha256(reference_path.read_bytes()).hexdigest()
    native = NativeDeath(reference_path)
    output = root / 'work/output' / clip_name
    output.mkdir(exist_ok=False)
    target = output / f'{clip_name}.blend'
    shutil.copy2(source, target)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    rig = builder.find_rig()
    scene = bpy.context.scene
    action = rig.animation_data.action
    action.name = clip_name
    boundary = 56
    end = 104
    protected_frames = [index / 4 for index in range(boundary * 4 + 1)]
    protected = sample(rig, protected_frames)
    frame_set(boundary)

    # Match the evaluated spine before disabling its chest rotation constraints.
    # The approved prefix has a static torso; direct spine keys retain that pose.
    spine_matrices = {
        bone_name: rig.pose.bones[bone_name].matrix.copy()
        for bone_name in ('CTRL-Spine1', 'CTRL-Spine2')
    }
    for bone_name, matrix in spine_matrices.items():
        bone = rig.pose.bones[bone_name]
        for constraint in bone.constraints:
            if constraint.type == 'COPY_ROTATION':
                constraint.influence = 0.0
        bone.matrix = matrix
        bpy.context.view_layer.update()

    mapping = {
        'CTRL-Pelvis': 'Bip01_Pelvis',
        'CTRL-Spine1': 'Bip01_Spine',
        'CTRL-Spine2': 'Bip01_Spine1',
        'CTRL-Head': 'Bip01_Head',
        'CTRL-LegIK.L': 'Bip01_L_Foot',
        'CTRL-LegIK.R': 'Bip01_R_Foot',
        'CTRL-KneeTarget.L': None,
        'CTRL-KneeTarget.R': None,
        'CTRL-UpperArmFK.L': 'Bip01_L_UpperArm',
        'CTRL-ForearmFK.L': 'Bip01_L_Forearm',
        'CTRL-HandFK.L': 'Bip01_L_Hand',
        'CTRL-ArmIK.R': 'Bip01_R_Hand',
        'CTRL-ElbowTarget.R': None,
    }
    names = list(mapping)
    base = {name: rig.pose.bones[name].matrix.copy() for name in names}
    local = {
        name: {
            'location': rig.pose.bones[name].location.copy(),
            'rotation_quaternion': rig.pose.bones[name].rotation_quaternion.copy(),
            'scale': rig.pose.bones[name].scale.copy(),
        }
        for name in names
    }
    correction = {
        name: rig.pose.bones[deform].matrix.inverted() @ base[name]
        for name, deform in mapping.items()
        if deform
    }
    native_start = native.pose(0)
    alignment = Matrix.Translation(base['CTRL-Pelvis'].translation - native_start['Bip01_Pelvis'].translation)
    blade = rig.pose.bones['Bip01_Prop1'].matrix.to_3x3().col[2].normalized()
    body = next(obj for obj in bpy.data.objects if obj.name.startswith('OBJ-MaleBody'))


    def mesh_points():
        evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        transform = rig.matrix_world.inverted() @ body.matrix_world
        result = [transform @ vertex.co for vertex in mesh.vertices]
        evaluated.to_mesh_clear()
        return result


    floor = min(point.z for point in mesh_points())
    controlled_paths = {
        rig.pose.bones[name].path_from_id(prop)
        for name in names
        for prop in ('location', 'rotation_quaternion', 'scale')
    }
    frozen = {
        (fc.data_path, fc.array_index): freeze_and_trim(fc, boundary)
        for fc in curves(action)
        if fc.data_path in controlled_paths
    }
    for name in names:
        bone = rig.pose.bones[name]
        bone.rotation_mode = 'QUATERNION'
        for prop, value in local[name].items():
            setattr(bone, prop, value)
            bone.keyframe_insert(prop, frame=boundary, group=name)
            if not any(key[0] == bone.path_from_id(prop) for key in frozen):
                bone.keyframe_insert(prop, frame=0, group=name)

    previous = {name: local[name]['rotation_quaternion'].copy() for name in names}
    contact = []
    key_frames = [56, 61, 66, 69, 72, 75, 78, 81, 86, 92, 98, 104]
    for frame in key_frames[1:]:
        frame_set(frame)
        native_frame = min(33.0, (frame - boundary) * 0.8)
        pose = {bone: alignment @ matrix for bone, matrix in native.pose(native_frame).items()}
        amount = min(1.0, (frame - boundary) / 10)
        amount = amount * amount * (3 - 2 * amount)
        desired = {}
        for name, deform in mapping.items():
            if deform:
                desired[name] = pose[deform] @ correction[name]
        pelvis_delta = desired['CTRL-Pelvis'] @ base['CTRL-Pelvis'].inverted()
        arm_amount = min(1.0, max(0.0, (frame - boundary - 3) / 13))
        arm_amount = arm_amount * arm_amount * (3 - 2 * arm_amount)
        carried_hand = pelvis_delta @ base['CTRL-ArmIK.R']
        carried_hand.translation -= pelvis_delta.to_3x3() @ blade * min(8.0, (frame - boundary) * 1.6)
        desired['CTRL-ArmIK.R'] = carried_hand.lerp(desired['CTRL-ArmIK.R'], arm_amount)
        shoulder = pose['Bip01_R_UpperArm'].translation
        elbow = pose['Bip01_R_Forearm'].translation
        wrist = pose['Bip01_R_Hand'].translation
        axis = wrist - shoulder
        projected = shoulder + axis * (elbow - shoulder).dot(axis) / axis.length_squared
        bend = elbow - projected
        pole = elbow + bend.normalized() * 10
        carried_pole = pelvis_delta @ base['CTRL-ElbowTarget.R']
        desired['CTRL-ElbowTarget.R'] = carried_pole.copy()
        desired['CTRL-ElbowTarget.R'].translation = carried_pole.translation.lerp(pole, arm_amount)

        for side in ('L', 'R'):
            hip = pose[f'Bip01_{side}_Thigh'].translation
            knee = pose[f'Bip01_{side}_Calf'].translation
            ankle = pose[f'Bip01_{side}_Foot'].translation
            leg_axis = ankle - hip
            leg_projected = hip + leg_axis * (knee - hip).dot(leg_axis) / leg_axis.length_squared
            knee_bend = knee - leg_projected
            desired[f'CTRL-KneeTarget.{side}'] = base[f'CTRL-KneeTarget.{side}'].copy()
            desired[f'CTRL-KneeTarget.{side}'].translation = knee + knee_bend.normalized() * 15

        for name in names:
            bone = rig.pose.bones[name]
            target_matrix = base[name].lerp(desired[name], amount)
            bone.matrix = target_matrix
            if name not in ('CTRL-Pelvis', 'CTRL-ArmIK.R', 'CTRL-ElbowTarget.R', 'CTRL-LegIK.L', 'CTRL-LegIK.R', 'CTRL-KneeTarget.L', 'CTRL-KneeTarget.R'):
                # Keep anatomical attachments at their original local positions.
                bone.location = local[name]['location']
                bone.scale = local[name]['scale']
            bpy.context.view_layer.update()

        minimum = min(point.z for point in mesh_points())
        lift = max(0.0, floor - minimum)
        if native_frame >= 24:
            lift = floor - minimum
        independent = {
            name: rig.pose.bones[name].matrix.copy()
            for name in ('CTRL-Pelvis', 'CTRL-ArmIK.R', 'CTRL-ElbowTarget.R', 'CTRL-LegIK.L', 'CTRL-LegIK.R', 'CTRL-KneeTarget.L', 'CTRL-KneeTarget.R')
        }
        for name, matrix in independent.items():
            matrix.translation.z += lift
            rig.pose.bones[name].matrix = matrix
            bpy.context.view_layer.update()
        hand_control = rig.pose.bones['CTRL-ArmIK.R']
        shoulder_position = rig.pose.bones['IK-UpperArm.R'].head.copy()
        hand_offset = hand_control.head - shoulder_position
        if hand_offset.length > 23.5:
            hand_matrix = hand_control.matrix.copy()
            hand_matrix.translation = shoulder_position + hand_offset.normalized() * 23.5
            hand_control.matrix = hand_matrix
            bpy.context.view_layer.update()
        if native_frame >= 24:
            for ground_iteration in range(6):
                remaining = floor - min(point.z for point in mesh_points())
                if abs(remaining) < 0.01:
                    break
                adjusted_targets = {
                    target_name: rig.pose.bones[target_name].matrix.copy()
                    for target_name in independent
                }
                for target_name, target_matrix in adjusted_targets.items():
                    target_matrix.translation.z += remaining * 0.5
                    rig.pose.bones[target_name].matrix = target_matrix
                    bpy.context.view_layer.update()
        contact.append({
            'frame': frame,
            'native_frame': native_frame,
            'skin_minimum_z': min(point.z for point in mesh_points()),
            'ground_correction': lift,
        })
        for name in names:
            bone = rig.pose.bones[name]
            if previous[name].dot(bone.rotation_quaternion) < 0:
                bone.rotation_quaternion.negate()
            previous[name] = bone.rotation_quaternion.copy()
            for prop in ('location', 'rotation_quaternion', 'scale'):
                bone.keyframe_insert(prop, frame=frame, group=name)

    for fc in curves(action):
        if fc.data_path in controlled_paths:
            smooth_monotone(fc)
            if (fc.data_path, fc.array_index) in frozen:
                restore_prefix(fc, frozen[(fc.data_path, fc.array_index)], boundary)
    scene.frame_end = end
    scene.frame_preview_end = end
    action.use_frame_range = False
    for marker in list(scene.timeline_markers):
        if marker.frame > boundary:
            scene.timeline_markers.remove(marker)
    for frame, label in ((56, 'FALL_START'), (76, 'HIP_CONTACT_REFERENCE'), (86, 'BACK_CONTACT_REFERENCE'), (98, 'SETTLED')):
        scene.timeline_markers.new(label, frame=frame)
    after = sample(rig, protected_frames)
    prefix_error = max(
        matrix_error(before[bone], current[bone])
        for before, current in zip(protected, after)
        for bone in before
    )
    assert prefix_error < 0.001, ('Approved stabbing changed', prefix_error)
    reach = builder.validate_right_arm_reach(rig, {
        'frame_start': 0,
        'frame_end': end,
        'validate_every_frame': True,
        'tracks': [{'bone': 'CTRL-ArmIK.R', 'keyframes': [{'frame': 0, 'location_offset': [0, 0, 0]}]}],
    })
    previews = builder.render_body_previews(rig, {
        'frame_start': 0,
        'body_preview': {
            'views': ['front', 'right'],
            'frames': [{'frame': frame, 'name': 'FALL'} for frame in key_frames],
        },
    }, output)
    frame_set(56)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    builder.export_glb(rig, action, output)
    report = builder.validate_glb(output / f'{clip_name}.glb', clip_name)
    report.update({
        'source': str(source),
        'source_sha256': source_hash,
        'native_reference': 'game:media/anims_X/Zombie/Zombie_Death.X',
        'native_reference_sha256': reference_hash,
        'native_speed_scale': 0.8,
        'preserved_through_frame': boundary,
        'maximum_prefix_matrix_error': prefix_error,
        'authoring_frames': key_frames,
        'contact_samples': contact,
        'previews': previews,
        'right_arm_reach': reach,
        'in_game_verified': False,
    })
    settled_poses = sample(rig, [98 + index / 4 for index in range(25)])
    settled_error = max(
        matrix_error(settled_poses[0][bone], pose[bone])
        for pose in settled_poses
        for bone in pose
    )
    assert settled_error < 0.001, ('Ending hold moves', settled_error)
    report['final_hold_matrix_error'] = settled_error
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    assert hashlib.sha256(reference_path.read_bytes()).hexdigest() == reference_hash
    (output / 'validation.json').write_text(json.dumps(report, indent=4))
    print('BACKWARD_FALL_DRAFT_OK', json.dumps({'prefix_error': prefix_error, 'contact': contact}))








if __name__ == "__main__":
    raise RuntimeError(
        "Construction reference only. Adapt the poses and paths; do not replay historical frame assumptions."
    )
