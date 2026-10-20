"""Shared sparse-motion curve operations. No file I/O or animation-specific main."""

import bisect
import math
import bpy


def curves(action):
    return [
        fc
        for layer in action.layers
        for strip in layer.strips
        for bag in strip.channelbags
        for fc in bag.fcurves
    ]


def sample(rig, frames):
    result = []
    for frame in frames:
        bpy.context.scene.frame_set(math.floor(frame), subframe=frame % 1)
        bpy.context.view_layer.update()
        result.append({b.name: b.matrix.copy() for b in rig.pose.bones})
    return result


def matrix_error(a, b):
    return max(abs(a[r][c] - b[r][c]) for r in range(4) for c in range(4))


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def split_polygon(p, t):
    a, b, c = lerp(p[0], p[1], t), lerp(p[1], p[2], t), lerp(p[2], p[3], t)
    d, e = lerp(a, b, t), lerp(b, c, t)
    middle = lerp(d, e, t)
    return [p[0], a, d, middle], [middle, e, c, p[3]]


def split_at_time(p, x):
    assert p[0][0] <= p[1][0] <= p[2][0] <= p[3][0], "Unsupported non-monotone Bezier handles"
    low, high = 0.0, 1.0
    for _ in range(55):
        t = (low + high) * 0.5
        left, right = split_polygon(p, t)
        if left[-1][0] < x:
            low = t
        else:
            high = t
    return split_polygon(p, (low + high) * 0.5)


def affine_map(knots):
    xs = [a for a, b in knots]

    def mapping(x):
        index = max(0, min(len(knots) - 2, bisect.bisect_right(xs, x) - 1))
        a, b = knots[index], knots[index + 1]
        return a[1] + (x - a[0]) * (b[1] - a[1]) / (b[0] - a[0])

    return mapping


def repair_curve_handles(fc, reference):
    """Restore reference tangents to edited key intervals; never move keys."""
    keys = list(fc.keyframe_points)
    assert len(keys) == len(reference) and len(keys) >= 2
    for i, (key, old) in enumerate(zip(keys, reference)):
        assert abs(key.co.y - old["co"][1]) < 0.000001, "Reference key values differ"
        assert key.interpolation == old["mode"], "Reference interpolation differs"
        key.handle_left_type = key.handle_right_type = "FREE"
        for side in ("left", "right"):
            neighbor = max(0, i - 1) if side == "left" else min(len(keys) - 1, i + 1)
            if neighbor == i:
                neighbor = 1 if i == 0 else len(keys) - 2
            old_span = reference[neighbor]["co"][0] - old["co"][0]
            new_span = keys[neighbor].co.x - key.co.x
            assert old_span * new_span > 0, "Key order changed"
            ratio = new_span / old_span
            handle = old[side]
            position = (
                key.co.x + (handle[0] - old["co"][0]) * ratio,
                key.co.y + handle[1] - old["co"][1],
            )
            setattr(key, "handle_" + side, position)
    fc.update()


# Move the keys and handles together to keep the curve shape.
def retime_curve(fc, knots):
    assert (
        not fc.modifiers and not fc.sampled_points
    ), "Time-dependent modifiers/sampled curves need a separate retimer"
    mapping = affine_map(knots)
    old = [
        {
            "co": tuple(k.co),
            "left": tuple(k.handle_left),
            "right": tuple(k.handle_right),
            "mode": k.interpolation,
        }
        for k in fc.keyframe_points
    ]
    if not old:
        return 0
    points = {k["co"][0]: dict(k) for k in old}
    phase_boundaries = [a for a, b in knots[1:-1]]
    segments = []
    for start, finish in zip(old, old[1:]):
        x0, y0 = start["co"]
        x1, y1 = finish["co"]
        mode = start["mode"]
        assert mode in ("BEZIER", "LINEAR", "CONSTANT"), ("Unsupported interpolation", mode)
        breaks = [x for x in phase_boundaries if x0 < x < x1]
        constant = mode == "CONSTANT" or (
            y0 == y1 and (mode == "LINEAR" or (start["right"][1] == y0 and finish["left"][1] == y0))
        )
        if not breaks or constant:
            segments.append((x0, x1, constant))
            continue
        if mode == "LINEAR":
            previous = x0
            for x in breaks:
                co = (x, y0 + (y1 - y0) * (x - x0) / (x1 - x0))
                points[x] = {"co": co, "left": co, "right": co, "mode": mode}
                segments.append((previous, x, False))
                previous = x
            segments.append((previous, x1, False))
        else:
            polygon = [start["co"], start["right"], finish["left"], finish["co"]]
            previous = x0
            for x in breaks:
                left, polygon = split_at_time(polygon, x)
                points[previous]["right"] = left[1]
                co = (x, left[-1][1])
                points[x] = {"co": co, "left": left[2], "right": polygon[1], "mode": mode}
                segments.append((previous, x, False))
                previous = x
            points[previous]["right"] = polygon[1]
            points[x1]["left"] = polygon[2]
            segments.append((previous, x1, False))
    # Map each segment's handles with THAT segment's affine transform. Applying
    # the global map to a handle beyond a phase boundary changes its tangent.
    transformed = {
        x: {
            "co": (mapping(x), k["co"][1]),
            "left": (mapping(k["left"][0]), k["left"][1]),
            "right": (mapping(k["right"][0]), k["right"][1]),
            "mode": k["mode"],
        }
        for x, k in points.items()
    }
    for a, b, constant in segments:
        na, nb = mapping(a), mapping(b)
        slope = (nb - na) / (b - a)
        for x, side in ((a, "right"), (b, "left")):
            handle = points[x][side]
            transformed[x][side] = (na + (handle[0] - a) * slope, handle[1])
    fc.keyframe_points.clear()
    for x in sorted(transformed):
        value = transformed[x]
        k = fc.keyframe_points.insert(*value["co"], options={"FAST"})
        k.handle_left_type = k.handle_right_type = "FREE"
        k.interpolation = value["mode"]
        k.handle_left, k.handle_right = value["left"], value["right"]
    fc.update()
    return len(transformed) - len(old)


def update_scene(frame):
    bpy.context.scene.frame_set(int(frame), subframe=frame % 1)
    bpy.context.view_layer.update()


def describe(rig, frames):
    result = {}
    for frame in frames:
        update_scene(frame)
        hand = rig.pose.bones["Bip01_R_Hand"]
        fore = rig.pose.bones["IK-Forearm.R"]
        direction = hand.matrix.to_3x3().col[0].normalized()
        result[str(frame)] = {
            # A rig-space alignment diagnostic, NOT a clinical joint angle.
            "finger_axis_forearm_angle_degrees": math.degrees(
                direction.angle((fore.tail - fore.head).normalized())
            ),
            "hand_control_quaternion": list(rig.pose.bones["CTRL-ArmIK.R"].rotation_quaternion),
            "hand_position": list(hand.head),
            "prop_position": list(rig.pose.bones["Bip01_Prop1"].head),
        }
    return result


def smooth_monotone(fc):
    """PCHIP-style slopes: no component overshoot or added motion keys."""
    keys = list(fc.keyframe_points)
    if len(keys) < 2:
        return
    xs, ys = [k.co.x for k in keys], [k.co.y for k in keys]
    spans = [b - a for a, b in zip(xs, xs[1:])]
    secants = [(b - a) / h for a, b, h in zip(ys, ys[1:], spans)]
    slopes = [0.0] * len(keys)
    for i in range(1, len(keys) - 1):
        left, right = secants[i - 1 : i + 1]
        if left * right > 0:
            w1, w2 = 2 * spans[i] + spans[i - 1], spans[i] + 2 * spans[i - 1]
            slopes[i] = (w1 + w2) / (w1 / left + w2 / right)
    for i, k in enumerate(keys):
        k.interpolation = "BEZIER"
        k.handle_left_type = k.handle_right_type = "FREE"
        hleft = spans[max(0, i - 1)] / 3
        hright = spans[min(i, len(spans) - 1)] / 3
        k.handle_left = (xs[i] - hleft, ys[i] - slopes[i] * hleft)
        k.handle_right = (xs[i] + hright, ys[i] + slopes[i] * hright)
    fc.update()


def frame_set(frame):
    bpy.context.scene.frame_set(math.floor(frame), subframe=frame % 1)
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


def snapshot(fc):
    return [
        {
            "co": tuple(k.co),
            "left": tuple(k.handle_left),
            "right": tuple(k.handle_right),
            "mode": k.interpolation,
        }
        for k in fc.keyframe_points
    ]
