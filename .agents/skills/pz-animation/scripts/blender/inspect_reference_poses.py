"""Print right-arm joint positions for the one-frame reference actions."""

import bpy

rig = next(
    obj
    for obj in bpy.data.objects
    if obj.type == "ARMATURE" and obj.name.startswith("OBJ-HumanRig")
)

for action_name in ("Idle", "Aim1Hand", "AimBat", "Surrender", "T-Pose"):
    action = bpy.data.actions[action_name]
    rig.animation_data.action = action
    rig.animation_data.action_slot = action.slots[0]
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    shoulder = rig.pose.bones["CTRL-UpperArmFK.R"].head
    elbow = rig.pose.bones["CTRL-ForearmFK.R"].head
    hand = rig.pose.bones["CTRL-HandFK.R"].head
    ik_hand = rig.pose.bones["CTRL-ArmIK.R"].head
    driven_elbow = rig.pose.bones["IK-Forearm.R"].head
    driven_hand = rig.pose.bones["IK-Forearm.R"].tail
    print(
        "REFERENCE_POSE",
        action_name,
        "shoulder",
        tuple(round(value, 2) for value in shoulder),
        "elbow",
        tuple(round(value, 2) for value in elbow),
        "hand",
        tuple(round(value, 2) for value in hand),
        "ik_hand",
        tuple(round(value, 2) for value in ik_hand),
        "driven_elbow",
        tuple(round(value, 2) for value in driven_elbow),
        "driven_hand",
        tuple(round(value, 2) for value in driven_hand),
        "ik_weight",
        rig.pz_human_props.arm_ik_r,
    )
