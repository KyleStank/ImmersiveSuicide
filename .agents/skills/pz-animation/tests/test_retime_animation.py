"""Synthetic curve tests; Blender background only, no files read/saved."""

import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/blender"))
from motion_curves import curves, affine_map, retime_curve, repair_curve_handles

knots = [(0, 0), (25, 10), (50, 30), (100, 40)]
mapping = affine_map(knots)
results = []
for mode, constant in [("BEZIER", False), ("LINEAR", False), ("CONSTANT", False), ("BEZIER", True)]:
    obj = bpy.data.objects.new("RetimeSynthetic", None)
    bpy.context.scene.collection.objects.link(obj)
    obj["value"] = 5.0 if constant else 1.0
    obj.keyframe_insert(data_path='["value"]', frame=0)
    obj["value"] = 5.0 if constant else 20.0
    obj.keyframe_insert(data_path='["value"]', frame=100)
    fc = curves(obj.animation_data.action)[0]
    for k in fc.keyframe_points:
        k.interpolation = mode
        k.handle_left_type = k.handle_right_type = "FREE"
    first, last = fc.keyframe_points
    first.handle_right = (15, 5 if constant else 28)
    last.handle_left = (75, 5 if constant else -12)
    fc.update()
    times = [i / 8 for i in range(801)]
    expected = [fc.evaluate(t) for t in times]
    added = retime_curve(fc, knots)
    maximum = max(abs(a - fc.evaluate(mapping(t))) for t, a in zip(times, expected))
    assert maximum < 0.0001, (mode, constant, maximum)
    assert added == (0 if constant or mode == "CONSTANT" else 2), (mode, constant, added)
    results.append((mode, constant, added, maximum))
print("RETIME_SYNTHETIC_TESTS_OK", results)

# Simulate manually moving FREE keys without rescaling the adjacent handles.
obj = bpy.data.objects.new("HandleRepairSynthetic", None)
bpy.context.scene.collection.objects.link(obj)
for x, y in [(0, 0.0), (30, 12.0), (100, 20.0)]:
    obj["value"] = y
    obj.keyframe_insert(data_path='["value"]', frame=x)
fc = curves(obj.animation_data.action)[0]
for k in fc.keyframe_points:
    k.interpolation = "BEZIER"
    k.handle_left_type = k.handle_right_type = "FREE"
fc.keyframe_points[0].handle_right = (10, 5)
fc.keyframe_points[1].handle_left = (20, 8)
fc.keyframe_points[1].handle_right = (53, 16)
fc.keyframe_points[2].handle_left = (77, 18)
fc.update()
reference = [
    {
        "co": tuple(k.co),
        "left": tuple(k.handle_left),
        "right": tuple(k.handle_right),
        "mode": k.interpolation,
    }
    for k in fc.keyframe_points
]
times = [i / 8 for i in range(801)]
expected = [fc.evaluate(t) for t in times]
for key, old, new_time in zip(fc.keyframe_points, reference, [0, 10, 50]):
    shift = new_time - old["co"][0]
    key.co.x = new_time
    key.handle_left = (old["left"][0] + shift, old["left"][1])
    key.handle_right = (old["right"][0] + shift, old["right"][1])
fc.update()
edited_keys = [tuple(k.co) for k in fc.keyframe_points]
repair_curve_handles(fc, reference)
mapping = affine_map([(0, 0), (30, 10), (100, 50)])
maximum = max(abs(a - fc.evaluate(mapping(t))) for t, a in zip(times, expected))
assert maximum < 0.0001, maximum
assert edited_keys == [tuple(k.co) for k in fc.keyframe_points]
print("HANDLE_REPAIR_SYNTHETIC_TEST_OK", maximum)
