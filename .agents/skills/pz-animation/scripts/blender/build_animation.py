"""Build one Project Zomboid GLB from a JSON spec inside Blender.

Blender must open a copied working file, never skill assets/rig/PZ_HumanRigV4.blend.
"""

import argparse
import json
import math
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recipe

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

TEMPLATE_NAME = "PZ_HumanRigV4.blend"
SKILL_ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = SKILL_ROOT / "work" / "output"
RIG_NAME_PREFIX = "OBJ-HumanRig"


def parse_args():
    command_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--name")
    return parser.parse_args(command_args)


def fail(message):
    raise RuntimeError(message)


def load_spec(path):
    return recipe.validate_template(recipe.read_recipe(path))


def find_rig():
    rigs = [
        obj
        for obj in bpy.data.objects
        if obj.type == "ARMATURE" and obj.name.startswith(RIG_NAME_PREFIX)
    ]
    if len(rigs) != 1:
        fail(f"Expected exactly one Paddlefruit armature, found {len(rigs)}.")
    return rigs[0]


def snap_right_arm_ik_to_current_fk(rig):
    """Match the right-arm IK controls to the currently evaluated FK pose."""
    bones = rig.pose.bones
    upper = bones["CTRL-UpperArmFK.R"]
    forearm = bones["CTRL-ForearmFK.R"]
    hand = bones["CTRL-HandFK.R"]
    ik_hand = bones["CTRL-ArmIK.R"]
    pole = bones["CTRL-ElbowTarget.R"]

    # Evaluate the reference pose in FK before reading its joint positions.
    rig.pz_human_props.arm_ik_r = 0.0
    rig.update_tag()
    bpy.context.view_layer.update()

    shoulder = upper.head.copy()
    elbow = forearm.head.copy()
    wrist = hand.head.copy()
    shoulder_to_wrist = wrist - shoulder
    denominator = shoulder_to_wrist.length_squared
    if denominator < 1e-8:
        fail("Cannot initialize right-arm IK: shoulder and wrist overlap.")

    elbow_projection = shoulder + shoulder_to_wrist * (
        (elbow - shoulder).dot(shoulder_to_wrist) / denominator
    )
    bend_direction = elbow - elbow_projection
    if bend_direction.length < 1e-5:
        fail("Cannot initialize right-arm IK: the reference arm is perfectly straight.")

    ik_hand.matrix = hand.matrix.copy()
    pole_matrix = pole.matrix.copy()
    pole_matrix.translation = elbow + bend_direction.normalized() * 15.0
    pole.matrix = pole_matrix
    bpy.context.view_layer.update()

    rig.pz_human_props.arm_ik_r = 1.0
    rig.update_tag()
    bpy.context.view_layer.update()


def sample_reference_hand_controls(rig, spec):
    reference = spec.get("reference_hand_pose")
    if not reference:
        return []
    bpy.context.scene.frame_set(int(reference.get("frame", 20)))
    bpy.context.view_layer.update()
    basis = Matrix(((1, 0, 0), (0, 0, 1), (0, 1, 0)))
    controls = []

    def rotation_error(target, current):
        difference = target @ current.inverted()
        difference.normalize()
        if difference.w < 0:
            difference.negate()
        return difference.to_exponential_map()

    for sample in reference["bones"]:
        deform = rig.pose.bones[sample["deform_bone"]]
        control = rig.pose.bones[sample["control_bone"]]
        if control.name not in {"CTRL-Thumb.R", "CTRL-Fingers.R"}:
            fail("Reference grip only supports right thumb/fingers.")
        source = Quaternion(sample["game_rotation_quaternion"]).normalized()
        target = (basis @ source.to_matrix() @ basis).to_quaternion()
        control.rotation_mode = "QUATERNION"

        def evaluated_rotation():
            bpy.context.view_layer.update()
            return (deform.parent.matrix.inverted() @ deform.matrix).to_quaternion()

        # Solve against the evaluated deform bone, accounting for V4's
        # LOCAL_OWNER_ORIENT constraint and different control rest axes.
        # Sampling only two bones keeps all approved arm/prop motion untouched.
        for _ in range(24):
            current = evaluated_rotation()
            residual = rotation_error(target, current)
            if residual.length < 1e-5:
                break
            original = control.rotation_quaternion.copy()
            columns = []
            epsilon = 0.02
            for axis in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))):
                control.rotation_quaternion = Quaternion(axis, epsilon) @ original
                columns.append(rotation_error(evaluated_rotation(), current) / epsilon)
            control.rotation_quaternion = original
            jacobian = Matrix(columns).transposed()
            step = jacobian.inverted() @ residual
            if step.length > 0.6:
                step *= 0.6 / step.length
            control.rotation_quaternion = Quaternion(step) @ original
            control.rotation_quaternion.normalize()
        error = rotation_error(target, evaluated_rotation()).length
        if error > 0.001:
            fail(f"Could not retarget {control.name}; residual {math.degrees(error):.3f} degrees.")
        print(f"REFERENCE_GRIP {control.name} residual_degrees={math.degrees(error):.6f}")
        controls.append(
            {"bone": control.name, "rotation_quaternion": list(control.rotation_quaternion)}
        )
    return controls


def create_action(rig, spec):
    old_action = bpy.data.actions.get(spec["name"])
    if old_action:
        bpy.data.actions.remove(old_action)

    base_action_name = spec.get("base_action")
    source_action = None
    if base_action_name:
        source_action = bpy.data.actions.get(base_action_name)
        if source_action is None:
            fail(f"Base action not found: {base_action_name}")

    rig.animation_data_create()

    if base_action_name:
        # A base action is a pose reference only. Never copy its curves into the
        # generated action: doing so would silently add head, feet, and every
        # other control keyed by the source animation.
        rig.animation_data.action = source_action
        if source_action.slots:
            rig.animation_data.action_slot = source_action.slots[0]
        bpy.context.scene.frame_set(int(spec.get("base_action_frame", 1)))
        bpy.context.view_layer.update()

    # Sample FK first so the IK controls can preserve the reference arm pose.
    rig_settings = spec.get("rig_settings", {})
    if base_action_name and float(rig_settings.get("arm_ik_r", 0.0)) == 1.0:
        snap_right_arm_ik_to_current_fk(rig)

    rig.pz_human_props.arm_ik_l = float(rig_settings.get("arm_ik_l", 0.0))
    rig.pz_human_props.arm_ik_r = float(rig_settings.get("arm_ik_r", 0.0))
    bpy.context.view_layer.update()

    # Establish the approved hand-relative prop attachment before deriving hand
    # poses from desired prop positions. Endpoint keys are added below as usual.
    for control in spec.get("constant_controls", []):
        if control["bone"] == "CTRL-Prop.R":
            prop_control = rig.pose.bones["CTRL-Prop.R"]
            prop_control.rotation_mode = "QUATERNION"
            if "location" in control:
                prop_control.location = control["location"]
            prop_control.rotation_quaternion = control["rotation_quaternion"]
    bpy.context.view_layer.update()

    base_rotations = {}
    base_locations = {}
    base_matrices = {}
    for track in spec.get("tracks", []):
        bone_name = track.get("bone", "")
        bone = rig.pose.bones.get(bone_name)
        if bone is None:
            fail(f"Rig control not found: {bone_name}")
        base_rotations[bone_name] = bone.rotation_quaternion.copy()
        base_locations[bone_name] = bone.location.copy()
        base_matrices[bone_name] = bone.matrix.copy()

    # Start with a genuinely empty action. Only explicitly requested controls
    # will appear in Blender's Action Editor.
    action = bpy.data.actions.new(spec["name"])
    rig.animation_data.action = action
    for bone_name in base_matrices:
        rig.pose.bones[bone_name].matrix = base_matrices[bone_name]
    bpy.context.view_layer.update()

    for track in spec.get("tracks", []):
        bone_name = track["bone"]
        bone = rig.pose.bones[bone_name]
        bone.rotation_mode = "QUATERNION"
        base_rotation = base_rotations[bone_name]
        base_location = base_locations[bone_name]
        base_matrix = base_matrices[bone_name]

        for keyframe in track.get("keyframes", []):
            frame = int(keyframe["frame"])
            if frame < spec["frame_start"] or frame > spec["frame_end"]:
                fail(f"Keyframe {frame} for {bone_name} lies outside the animation range.")

            if "prop_pose" in keyframe:
                if bone_name != "CTRL-ArmIK.R":
                    fail("prop_pose supports only the right-hand IK control.")
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()
                pose = keyframe["prop_pose"]
                hand = rig.pose.bones["Bip01_R_Hand"]
                prop = rig.pose.bones["Bip01_Prop1"]
                hand_to_prop = hand.matrix.inverted() @ prop.matrix
                blade = Vector(pose["blade_direction"]).normalized()
                normal = Vector(pose["face_normal"]).normalized()
                normal -= blade * normal.dot(blade)
                if normal.length < 1e-5:
                    fail("Prop blade direction and face normal must not be parallel.")
                normal.normalize()
                # Corrected preview basis: raw blade +Y maps to prop +Z;
                # raw blade surface normal +X remains prop +X.
                target = Matrix((normal, blade.cross(normal), blade)).transposed().to_4x4()
                target.translation = rig.pose.bones[pose["anchor_bone"]].head + Vector(
                    pose["offset"]
                )
                target_hand = target @ hand_to_prop.inverted()
                control_matrix = target_hand @ hand.matrix.inverted() @ bone.matrix
                bone.matrix = control_matrix
                bpy.context.view_layer.update()
                bone.keyframe_insert(data_path="location", frame=frame, group=bone_name)
                bone.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=bone_name)

            if keyframe.get("align_hand_to_forearm"):
                if bone_name != "CTRL-ArmIK.R":
                    fail("align_hand_to_forearm supports only the right-hand IK control.")
                # Position tracks must precede this orientation track. Evaluate
                # their keyed pose, start from the reference wrist orientation,
                # then apply the shortest rotation that straightens the wrist.
                bpy.context.scene.frame_set(frame)
                bone.rotation_quaternion = base_rotation.copy()
                bpy.context.view_layer.update()
                hand = rig.pose.bones["Bip01_R_Hand"]
                forearm = rig.pose.bones["IK-Forearm.R"]
                fingers = (hand.matrix.to_3x3() @ Vector((1, 0, 0))).normalized()
                arm_direction = (forearm.tail - forearm.head).normalized()
                correction = fingers.rotation_difference(arm_direction)
                target_matrix = correction.to_matrix().to_4x4() @ bone.matrix
                target_matrix.translation = bone.matrix.translation
                bone.matrix = target_matrix
                bpy.context.view_layer.update()
                bone.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=bone_name)

            rotation_degrees = keyframe.get("rotation_degrees")
            if "semantic_rotation" in keyframe:
                if bone_name != "CTRL-ArmIK.R":
                    fail("semantic_rotation currently supports only the right-hand IK control.")
                semantic_rotation = keyframe["semantic_rotation"]
                rotation_degrees = [
                    float(semantic_rotation.get("roll", 0.0)),
                    float(semantic_rotation.get("pitch", 0.0)),
                    float(semantic_rotation.get("yaw", 0.0)),
                ]

            if rotation_degrees is not None:
                degrees = rotation_degrees
                if not isinstance(degrees, list) or len(degrees) != 3:
                    fail(f"{bone_name} frame {frame} requires three rotation_degrees values.")

                delta = Euler(
                    tuple(math.radians(float(value)) for value in degrees), "XYZ"
                ).to_quaternion()
                bone.rotation_quaternion = base_rotation @ delta
                bone.keyframe_insert(
                    data_path="rotation_quaternion",
                    frame=frame,
                    group=bone_name,
                )

            if "location_offset" in keyframe:
                offset = keyframe["location_offset"]
                if not isinstance(offset, list) or len(offset) != 3:
                    fail(f"{bone_name} frame {frame} requires three location_offset values.")
                bone.location = base_location + type(base_location)(
                    float(value) for value in offset
                )
                bone.keyframe_insert(
                    data_path="location",
                    frame=frame,
                    group=bone_name,
                )

            if "semantic_offset" in keyframe:
                if bone_name != "CTRL-ArmIK.R":
                    fail("semantic_offset currently supports only the right-hand IK control.")
                semantic = keyframe["semantic_offset"]
                # Semantic movement is applied in armature space so it remains
                # stable after snapping the IK control to a non-T-pose base.
                target_matrix = base_matrix.copy()
                target_matrix.translation += Vector(
                    (
                        -float(semantic.get("outward", 0.0)),
                        -float(semantic.get("forward", 0.0)),
                        float(semantic.get("up", 0.0)),
                    )
                )
                bone.matrix = target_matrix
                bpy.context.view_layer.update()
                bone.keyframe_insert(
                    data_path="location",
                    frame=frame,
                    group=bone_name,
                )

            if "elbow_height" in keyframe:
                if bone_name != "CTRL-ElbowTarget.R":
                    fail("elbow_height currently supports only the right elbow target.")
                target_matrix = base_matrix.copy()
                target_matrix.translation += Vector((0.0, 0.0, float(keyframe["elbow_height"])))
                bone.matrix = target_matrix
                bpy.context.view_layer.update()
                bone.keyframe_insert(
                    data_path="location",
                    frame=frame,
                    group=bone_name,
                )

            if not any(
                key in keyframe
                for key in (
                    "rotation_degrees",
                    "semantic_rotation",
                    "location_offset",
                    "semantic_offset",
                    "elbow_height",
                    "align_hand_to_forearm",
                    "prop_pose",
                )
            ):
                fail(f"{bone_name} frame {frame} has no supported transform.")

    # Fixed prop corrections are local to the hand-parented control, not an
    # armature/world-space pose sampled at one frame. Two identical endpoint
    # keys preserve the correction while the hand follows its existing motion.
    animated_controls = {track["bone"] for track in spec.get("tracks", [])}
    reference_controls = sample_reference_hand_controls(rig, spec)
    for control in spec.get("constant_controls", []) + reference_controls:
        bone_name = control["bone"]
        if (
            bone_name not in {"CTRL-Prop.R", "CTRL-Thumb.R", "CTRL-Fingers.R"}
            or bone_name in animated_controls
        ):
            fail("Fixed grip controls require otherwise unanimated right prop/thumb/fingers.")
        bone = rig.pose.bones[bone_name]
        bone.rotation_mode = "QUATERNION"
        if "location" in control:
            bone.location = Vector(control["location"])
        bone.rotation_quaternion = control["rotation_quaternion"]
        for frame in (int(spec["frame_start"]), int(spec["frame_end"])):
            if "location" in control:
                bone.keyframe_insert(data_path="location", frame=frame, group=bone_name)
            bone.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=bone_name)

    static_count = preserve_static_pose(rig, action, spec["frame_start"], spec["frame_end"])
    print(f"STATIC_POSE_COMPONENTS {static_count}")
    bpy.context.scene.frame_start = int(spec["frame_start"])
    bpy.context.scene.frame_end = int(spec["frame_end"])
    bpy.context.scene.render.fps = 30
    bpy.context.scene.render.fps_base = 1

    for marker in list(bpy.context.scene.timeline_markers):
        bpy.context.scene.timeline_markers.remove(marker)
    for marker in spec.get("markers", []):
        bpy.context.scene.timeline_markers.new(marker["name"], frame=int(marker["frame"]))

    # Smooth ordinary movement while keeping the generated action editable.
    interpolation = spec.get("interpolation", "BEZIER")
    if interpolation not in {"BEZIER", "LINEAR", "CONSTANT"}:
        fail(f"Unsupported interpolation mode: {interpolation}")
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for fcurve in channelbag.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        keyframe.interpolation = interpolation

    return action


def preserve_static_pose(rig, action, start, end):
    """Carry non-default, otherwise unkeyed controller components into NLA export.

    These two endpoint keys describe a pose, not dense authored motion. Never
    key over a moving component. Shared by template builds and future authors.
    """
    existing = {
        (fc.data_path, fc.array_index)
        for layer in action.layers
        for strip in layer.strips
        for bag in strip.channelbags
        for fc in bag.fcurves
    }
    count = 0
    for bone in rig.pose.bones:
        if not bone.name.startswith("CTRL-"):
            continue
        rotation = (
            "rotation_quaternion"
            if bone.rotation_mode == "QUATERNION"
            else "rotation_axis_angle" if bone.rotation_mode == "AXIS_ANGLE" else "rotation_euler"
        )
        for prop in ("location", rotation, "scale"):
            values = tuple(getattr(bone, prop))
            default = (
                (1, 0, 0, 0)
                if prop == "rotation_quaternion"
                else (
                    (0, 0, 1, 0)
                    if prop == "rotation_axis_angle"
                    else (1, 1, 1) if prop == "scale" else (0,) * len(values)
                )
            )
            for index, value in enumerate(values):
                if (bone.path_from_id(prop), index) not in existing and abs(
                    value - default[index]
                ) > 1e-7:
                    for frame in (start, end):
                        bone.keyframe_insert(prop, index=index, frame=frame, group=bone.name)
                    count += 1
    for prop in ("arm_ik_l", "arm_ik_r", "leg_ik_l", "leg_ik_r"):
        path = "pz_human_props." + prop
        if (path, 0) not in existing:
            for frame in (start, end):
                rig.keyframe_insert(path, frame=frame, group="Rig switches")
    return count


def validate_right_arm_reach(rig, spec):
    maximum_reach = rig.data.bones["IK-UpperArm.R"].length + rig.data.bones["IK-Forearm.R"].length
    measurements = []
    frames = sorted(
        {
            int(keyframe["frame"])
            for track in spec.get("tracks", [])
            if track.get("bone") == "CTRL-ArmIK.R"
            for keyframe in track.get("keyframes", [])
            if "semantic_offset" in keyframe
            or "location_offset" in keyframe
            or "prop_pose" in keyframe
        }
    )

    if spec.get("validate_every_frame") and frames:
        frames = list(range(int(spec["frame_start"]), int(spec["frame_end"]) + 1))
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        target = rig.pose.bones["CTRL-ArmIK.R"].head
        shoulder = rig.pose.bones["IK-UpperArm.R"].head
        distance = (target - shoulder).length
        measurements.append({"frame": frame, "distance": round(distance, 4)})
        if distance > maximum_reach + 0.25 and not spec.get("allow_unreachable", False):
            fail(
                f"Right-hand target at frame {frame} is unreachable: "
                f"distance {distance:.2f}, arm reach {maximum_reach:.2f}."
            )

    bpy.context.scene.frame_set(int(spec["frame_start"]))
    return {"maximum": round(maximum_reach, 4), "measurements": measurements}


def make_emission_material(name, color):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*color, 1.0)
    emission.inputs["Strength"].default_value = 1.5
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def create_orientation_proxy(rig):
    anchor = bpy.data.objects.new("CAL-RightHandOrientation", None)
    bpy.context.scene.collection.objects.link(anchor)
    constraint = anchor.constraints.new("COPY_TRANSFORMS")
    constraint.target = rig
    constraint.subtarget = "Bip01_R_Hand"

    axis_data = (
        ("X", (1.0, 0.03, 0.03), (9.0, 0.0, 0.0), (9.0, 0.7, 0.7)),
        ("Y", (0.03, 1.0, 0.03), (0.0, 7.0, 0.0), (0.7, 7.0, 0.7)),
        ("Z", (0.03, 0.2, 1.0), (0.0, 0.0, 5.0), (0.7, 0.7, 5.0)),
    )
    for axis, color, location, scale in axis_data:
        bpy.ops.mesh.primitive_cube_add()
        rod = bpy.context.object
        rod.name = f"CAL-HandAxis-{axis}"
        rod.parent = anchor
        rod.location = location
        rod.scale = scale
        rod.data.materials.append(make_emission_material(f"CAL-Mat-{axis}", color))

    return anchor


def point_camera_at(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def add_held_item_preview(rig, spec):
    """Attach a static game mesh to the exported prop bone for visual review."""
    item = spec.get("held_item_preview")
    if not item:
        return None
    model_path = Path(item["mesh_path"])
    text = model_path.read_text(encoding="utf-8-sig")
    # Deliberately narrow: one static text .X mesh, identity frame transform.
    # Fail instead of pretending to support skinned/animated/general .X files.
    if not text.startswith("xof 0303txt") or "SkinWeights {" in text:
        fail("Held-item preview requires a static text DirectX .X model.")
    mesh_matches = list(re.finditer(r"(?m)^\s*Mesh\s+\w+\s*\{", text))
    if len(mesh_matches) != 1:
        fail("Held-item preview requires exactly one mesh.")
    for match in re.finditer(r"(?m)^\s*FrameTransformMatrix\s*\{([^}]+)\}", text):
        values = [float(v) for v in re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", match[1])]
        identity = [1 if i // 4 == i % 4 else 0 for i in range(16)]
        if len(values) != 16 or any(abs(a - b) > 1e-6 for a, b in zip(values, identity)):
            fail("Non-identity .X frame transforms are not supported by the preview reader.")

    numbers = iter(
        re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text[mesh_matches[0].end() :])
    )
    vertex_count = int(next(numbers))
    raw_vertices = [tuple(float(next(numbers)) for _ in range(3)) for _ in range(vertex_count)]
    face_count = int(next(numbers))
    faces = [
        tuple(int(next(numbers)) for _ in range(int(next(numbers)))) for _ in range(face_count)
    ]

    # Raw game mesh coordinates are Y-up/left-handed; the Blender rig is
    # Z-up/right-handed. glTF export plus MAKE_LEFT_HANDED maps the rig to
    # game space as (x,z,y), so use its inverse (the same swap) on local
    # preview vertices. This is a reflection, not an extra prop-bone rotation.
    vertices = [(100 * x, 100 * z, 100 * y) for x, y, z in raw_vertices]
    faces = [tuple(reversed(face)) for face in faces]
    mesh = bpy.data.meshes.new("PREVIEW-KitchenKnifeMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_match = re.search(r"(?m)^\s*MeshTextureCoords(?:\s+\w+)?\s*\{([^}]+)\}", text)
    if uv_match:
        uv_numbers = iter(re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", uv_match[1]))
        uv_count = int(next(uv_numbers))
        if uv_count != vertex_count:
            fail("Preview mesh UV count does not match vertex count.")
        coords = [(float(next(uv_numbers)), 1 - float(next(uv_numbers))) for _ in range(uv_count)]
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for loop in mesh.loops:
            uv_layer.data[loop.index].uv = coords[loop.vertex_index]

    obj = bpy.data.objects.new("PREVIEW-KitchenKnife", mesh)
    bpy.context.scene.collection.objects.link(obj)
    # COPY_TRANSFORMS avoids Blender's bone-parent tail-origin offset. It
    # follows the actual deform prop's head and orientation, including rig scale.
    constraint = obj.constraints.new("COPY_TRANSFORMS")
    constraint.target = rig
    constraint.subtarget = "Bip01_Prop1"
    material = bpy.data.materials.new("PREVIEW-KitchenKnifeMaterial")
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(Path(item["texture_path"])), check_existing=True)
    texture.image.pack()
    texture.interpolation = "Closest"
    emission = tree.nodes.new("ShaderNodeEmission")
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    tree.links.new(texture.outputs["Color"], emission.inputs["Color"])
    tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    mesh.materials.append(material)
    bpy.context.view_layer.update()
    return {
        "model": "Knife",
        "mesh_path": str(model_path),
        "prop_bone": "Bip01_Prop1",
        "control_bone": "CTRL-Prop.R",
        "vertex_count": vertex_count,
        "face_count": face_count,
        "preview_only": True,
        "raw_x_to_rig_scale": 100.0,
        "game_to_blender_local_basis": [[1, 0, 0], [0, 0, 1], [0, 1, 0]],
        "preview_alignment_verified": False,
        "in_game_verified": False,
    }


def render_body_previews(rig, spec, output_dir):
    preview = spec.get("body_preview")
    if not preview:
        return []

    body = next(
        (obj for obj in bpy.data.objects if obj.name.startswith("OBJ-MaleBody")),
        None,
    )
    if body is None:
        fail("Cannot render body previews: GEO-MaleBody was not found.")

    # Fit all requested poses, including long horizontal prone bodies. Using
    # standing X width for a side camera crops most of a forward fall.
    corners = []
    for item in preview.get("frames", []):
        bpy.context.scene.frame_set(int(item["frame"]))
        bpy.context.view_layer.update()
        evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        corners.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
    if not corners:
        corners = [body.matrix_world @ Vector(corner) for corner in body.bound_box]
    minimum = Vector(tuple(min(point[index] for point in corners) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in corners) for index in range(3)))
    center = (minimum + maximum) * 0.5
    width = maximum.x - minimum.x
    depth = maximum.y - minimum.y
    height = maximum.z - minimum.z

    camera_data = bpy.data.cameras.new("CAL-BodyCamera")
    camera = bpy.data.objects.new("CAL-BodyCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(height * 1.12, width * 1.45)
    camera_distance = max(width, depth, height) * 3.0

    scene = bpy.context.scene
    scene.camera = camera
    scene.render.resolution_x = 560
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    preview_dir = output_dir / "body-preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    views = preview.get("views", ["front"])
    camera_offsets = {
        "front": Vector((0.0, -camera_distance, 0.0)),
        "right": Vector((-camera_distance, 0.0, 0.0)),
        "front_hand": Vector((0.0, -camera_distance, 0.0)),
        "right_hand": Vector((-camera_distance, 0.0, 0.0)),
        "top": Vector((0.0, 0.0, camera_distance)),
    }
    for view in views:
        if view not in camera_offsets:
            fail(f"Unsupported body preview view: {view}")
        camera.location = center + camera_offsets[view]
        point_camera_at(camera, center)
        for item in preview.get("frames", []):
            frame = int(item["frame"])
            label = item["name"]
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            target = center
            horizontal, vertical = (
                (depth, height)
                if view == "right"
                else ((width, depth) if view == "top" else (width, height))
            )
            camera.data.ortho_scale = max(vertical * 1.12, horizontal * 1.45)
            if view.endswith("_hand"):
                knife = bpy.data.objects.get("PREVIEW-KitchenKnife")
                if knife is None:
                    fail("Hand close-up requires a held-item preview.")
                evaluated = knife.evaluated_get(bpy.context.evaluated_depsgraph_get())
                points = [evaluated.matrix_world @ Vector(corner) for corner in knife.bound_box]
                points.append(rig.matrix_world @ rig.pose.bones["Bip01_R_Hand"].head)
                low = Vector(tuple(min(point[i] for point in points) for i in range(3)))
                high = Vector(tuple(max(point[i] for point in points) for i in range(3)))
                target = (low + high) * 0.5
                camera.data.ortho_scale = max(0.4, (high - low).length * 1.35)
            camera.location = target + camera_offsets[view]
            point_camera_at(camera, target)
            bpy.context.view_layer.update()
            scene.render.filepath = str(preview_dir / f"{frame:03d}_{label}_{view.upper()}.png")
            bpy.ops.render.render(write_still=True)
            rendered.append(scene.render.filepath)

    scene.frame_set(int(spec["frame_start"]))
    return rendered


def render_orientation_previews(rig, spec, output_dir):
    preview = spec.get("orientation_preview")
    if not preview:
        return []

    create_orientation_proxy(rig)
    camera = bpy.data.objects.get("CAL-RightHandCamera")
    if camera is None:
        camera_data = bpy.data.cameras.new("CAL-RightHandCamera")
        camera = bpy.data.objects.new("CAL-RightHandCamera", camera_data)
        bpy.context.scene.collection.objects.link(camera)

    camera.data.lens = 58.0
    camera_offset = Vector((0.0, -0.65, 0.12))

    scene = bpy.context.scene
    scene.camera = camera
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    preview_dir = output_dir / "orientation-preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for item in preview.get("frames", []):
        frame = int(item["frame"])
        label = item["name"]
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        hand_world = rig.matrix_world @ rig.pose.bones["Bip01_R_Hand"].head
        camera.location = hand_world + camera_offset
        point_camera_at(camera, hand_world)
        bpy.context.view_layer.update()
        scene.render.filepath = str(preview_dir / f"{frame:03d}_{label}.png")
        bpy.ops.render.render(write_still=True)
        rendered.append(scene.render.filepath)

    scene.frame_set(int(spec["frame_start"]))
    return rendered


def export_glb(rig, action, output_dir):
    (
        bpy.ops.object.mode_set(mode="OBJECT")
        if bpy.context.object and bpy.context.object.mode != "OBJECT"
        else None
    )
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    rig.animation_data.action = action
    rig.pz_human_props.file_output_path = str(output_dir)
    rig.pz_human_props.batch_export = False

    result = bpy.ops.zomboid.export_glb()
    if "FINISHED" not in result:
        fail(f"Paddlefruit exporter returned {result}.")


def read_glb_json(path):
    with path.open("rb") as handle:
        header = handle.read(20)
        if len(header) != 20 or header[:4] != b"glTF":
            fail("Exported file is not a GLB container.")
        json_length = struct.unpack_from("<I", header, 12)[0]
        if header[16:20] != b"JSON":
            fail("The first GLB chunk is not JSON.")
        return json.loads(handle.read(json_length).decode("utf-8").rstrip(" \x00"))


def validate_glb(path, expected_name):
    document = read_glb_json(path)
    animations = document.get("animations", [])
    names = [animation.get("name") for animation in animations]
    errors = []
    if len(animations) != 1:
        errors.append(f"Expected one animation, found {len(animations)}.")
    if names != [expected_name]:
        errors.append(f"Expected animation name {expected_name!r}, found {names!r}.")

    report = {
        "valid": not errors,
        "file": str(path),
        "animation_names": names,
        "animation_count": len(animations),
        "node_count": len(document.get("nodes", [])),
        "errors": errors,
    }
    if errors:
        fail(" ".join(errors))
    return report


# Build the working animation, export it and write the validation results.
def main():
    args = parse_args()
    spec_path = Path(args.spec).resolve()
    output_dir = Path(args.output_dir).resolve()
    current_blend = Path(bpy.data.filepath).resolve()
    spec = load_spec(spec_path)
    if args.name:
        spec["name"] = recipe.valid_name(args.name)
    recipe.require_template_copy(current_blend, output_dir, spec["name"])
    rig = find_rig()
    action = create_action(rig, spec)
    right_arm_reach = validate_right_arm_reach(rig, spec)
    held_item_preview = add_held_item_preview(rig, spec)
    body_previews = render_body_previews(rig, spec, output_dir)
    orientation_previews = render_orientation_previews(rig, spec, output_dir)

    # Save only the already-copied working file.
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.preferences.filepaths.file_preview_type = "NONE"
    bpy.ops.wm.save_as_mainfile(filepath=str(current_blend))
    export_glb(rig, action, output_dir)

    glb_path = output_dir / f"{spec['name']}.glb"
    if not glb_path.is_file():
        fail(f"Paddlefruit exporter did not create {glb_path}.")

    report = validate_glb(glb_path, spec["name"])
    report.update(
        {
            "blender_version": bpy.app.version_string,
            "fps": bpy.context.scene.render.fps,
            "frame_start": bpy.context.scene.frame_start,
            "frame_end": bpy.context.scene.frame_end,
            "working_blend": str(current_blend),
            "authored_keyframes": {
                track.get("name", track["bone"]): len(track.get("keyframes", []))
                for track in spec.get("tracks", [])
            },
            "markers": spec.get("markers", []),
            "right_arm_reach": right_arm_reach,
            "body_previews": body_previews,
            "orientation_previews": orientation_previews,
            "base_action": spec.get("base_action"),
            "constant_controls": spec.get("constant_controls", []),
            "reference_hand_pose": spec.get("reference_hand_pose"),
            "held_item_preview": held_item_preview,
        }
    )
    report["in_game_verified"] = False
    (output_dir / "recipe.resolved.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    with (output_dir / "validation.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print("PZ_ANIMATION_BUILD_OK")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
