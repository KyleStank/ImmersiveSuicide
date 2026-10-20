"""Repeat the maintainer's first hand/elbow stroke in a new review copy."""

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'scripts/blender'))
import build_animation as builder
from motion_curves import curves, frame_set, matrix_error, sample, snapshot


def main():
    name = 'Bob_IS_HeadStab_RepeatExample'
    source = root / 'assets/examples/head-stab/02-manual-first-stab.blend'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    output = root / 'work/output' / name
    output.mkdir(exist_ok=False)
    target = output / f'{name}.blend'
    shutil.copy2(source, target)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    rig = builder.find_rig()
    scene = bpy.context.scene
    action = rig.animation_data.action
    action.name = name
    prefix_frames = [index / 4 for index in range(97)]
    prefix = sample(rig, prefix_frames)
    reference_attack = sample(rig, [17 + index / 4 for index in range(29)])
    paths = {
        rig.pose.bones['CTRL-ArmIK.R'].path_from_id('location'),
        rig.pose.bones['CTRL-ElbowTarget.R'].path_from_id('location'),
    }
    local_reference = {}
    for frame in (17, 24):
        frame_set(frame)
        local_reference[str(frame)] = {
            bone_name: {
                'location': list(rig.pose.bones[bone_name].location),
                'rotation_quaternion': list(rig.pose.bones[bone_name].rotation_quaternion),
            }
            for bone_name in ('CTRL-ArmIK.R', 'CTRL-ElbowTarget.R')
        }


    def shifted(key, offset):
        result = copy.deepcopy(key)
        for field in ('co', 'left', 'right'):
            result[field] = (result[field][0] + offset, result[field][1])
        return result


    for fc in curves(action):
        if fc.data_path not in paths:
            continue
        original = snapshot(fc)
        keys = {key['co'][0]: key for key in original}
        ready = copy.deepcopy(keys[17])
        contact = copy.deepcopy(keys.get(24, {
            'co': (24, fc.evaluate(24)),
            'left': (24 - 7 / 3, fc.evaluate(24)),
            'right': (27, fc.evaluate(24)),
            'mode': 'BEZIER',
        }))
        is_elbow = 'CTRL-ElbowTarget.R' in fc.data_path
        if is_elbow:
            # Reverse the edited elbow approach over the nine-frame recovery.
            contact['right'] = (
                24 + (24 - contact['left'][0]) * 9 / 7,
                contact['left'][1],
            )
            recovery = shifted(ready, 16)
            recovery['left'] = (
                33 - (ready['right'][0] - 17) * 9 / 7,
                ready['right'][1],
            )
        else:
            recovery = copy.deepcopy(keys[33])
        recovery['right'] = shifted(ready, 16)['right']
        second_contact = shifted(contact, 16)
        second_recovery = shifted(recovery, 16)
        third_contact = shifted(contact, 32)
        third_contact['right'] = (57, contact['co'][1])
        final_hold = {
            'co': (59, contact['co'][1]),
            'left': (58, contact['co'][1]),
            'right': (60, contact['co'][1]),
            'mode': 'BEZIER',
        }
        result = [key for key in original if key['co'][0] < 24]
        result.extend([
            contact, recovery, second_contact,
            second_recovery, third_contact, final_hold,
        ])
        fc.keyframe_points.clear()
        for key in result:
            point = fc.keyframe_points.insert(*key['co'], options={'FAST'})
            point.interpolation = key['mode']
            point.handle_left_type = 'FREE'
            point.handle_right_type = 'FREE'
            point.handle_left = key['left']
            point.handle_right = key['right']
        fc.update()

    after = sample(rig, prefix_frames)
    prefix_error = max(
        matrix_error(before[bone], current[bone])
        for before, current in zip(prefix, after)
        for bone in before
    )
    assert prefix_error < 0.001, ('Edited lift/first stab changed', prefix_error)
    repeat_errors = {}
    for shift in (16, 32):
        repeated = sample(rig, [17 + shift + index / 4 for index in range(29)])
        error = max(
            matrix_error(reference[bone], repeated_pose[bone])
            for reference, repeated_pose in zip(reference_attack, repeated)
            for bone in reference
        )
        assert error < 0.001, ('Repeated stroke differs', shift, error)
        repeat_errors[str(shift)] = error

    frame_set(24)
    hand = rig.pose.bones['Bip01_R_Hand']
    grip_reference = {
        bone: hand.matrix.inverted() @ rig.pose.bones[bone].matrix
        for bone in ('Bip01_Prop1', 'Bip01_R_Finger0', 'Bip01_R_Finger1')
    }
    wrist_reference = rig.pose.bones['CTRL-ArmIK.R'].rotation_quaternion.copy()
    maximum_grip_error = 0.0
    maximum_wrist_error = 0.0
    for index in range(17 * 4, 59 * 4 + 1):
        frame_set(index / 4)
        for bone, reference in grip_reference.items():
            relative = hand.matrix.inverted() @ rig.pose.bones[bone].matrix
            maximum_grip_error = max(maximum_grip_error, matrix_error(reference, relative))
        wrist = rig.pose.bones['CTRL-ArmIK.R'].rotation_quaternion
        maximum_wrist_error = max(
            maximum_wrist_error,
            max(abs(wrist[axis] - wrist_reference[axis]) for axis in range(4)),
        )
    assert maximum_grip_error < 0.001, maximum_grip_error
    assert maximum_wrist_error < 0.00001, maximum_wrist_error
    reach = builder.validate_right_arm_reach(rig, {
        'frame_start': 0,
        'frame_end': 59,
        'validate_every_frame': True,
        'tracks': [{'bone': 'CTRL-ArmIK.R'}],
    })
    previews = builder.render_body_previews(rig, {
        'frame_start': 0,
        'body_preview': {
            'views': ['front', 'right'],
            'frames': [{'frame': frame, 'name': 'MOTION'} for frame in range(0, 60, 2)],
        },
    }, output)
    frame_set(24)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    builder.export_glb(rig, action, output)
    report = builder.validate_glb(output / f'{name}.glb', name)
    report.update({
        'source': str(source),
        'source_sha256': source_hash,
        'preserved_through_frame': 24,
        'preservation_samples': len(prefix_frames),
        'maximum_prefix_matrix_error': prefix_error,
        'repeated_attack_matrix_errors': repeat_errors,
        'maximum_hand_relative_grip_matrix_error': maximum_grip_error,
        'maximum_wrist_quaternion_component_error': maximum_wrist_error,
        'edited_local_control_reference': local_reference,
        'right_arm_reach': reach,
        'previews': previews,
        'in_game_verified': False,
    })
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    (output / 'validation.json').write_text(json.dumps(report, indent=4), encoding='utf-8')
    print('REPEAT_EDITED_STAB_OK', json.dumps({
        'prefix_error': prefix_error,
        'repeat_errors': repeat_errors,
        'grip_error': maximum_grip_error,
        'wrist_error': maximum_wrist_error,
    }))


if __name__ == "__main__":
    raise RuntimeError(
        "Construction reference only. Adapt the poses and paths; do not replay historical frame assumptions."
    )
