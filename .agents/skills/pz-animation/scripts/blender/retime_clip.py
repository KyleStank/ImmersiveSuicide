"""Copy and retime or export an existing clip without source edits or knife assumptions."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_animation as builder
import recipe
from motion_curves import curves, sample, matrix_error, affine_map, retime_curve


# Copy the source before changing timing or exporting.
def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("spec")
    parser.add_argument("--name")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    path = Path(args.spec).resolve()
    spec = recipe.read_recipe(path)
    spec["name"] = recipe.valid_name(args.name or spec.get("name"))
    knots = spec.get("time_map")
    if not args.export_only:
        recipe.validate_time_map(knots)
    source = recipe.resolve_path(spec["source_blend"], path.parent)
    if source.name == builder.TEMPLATE_NAME or source.suffix.lower() != ".blend":
        raise ValueError("Use template builder; never open immutable rig")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    output = recipe.output_path(spec["name"])
    output.mkdir(parents=True, exist_ok=False)
    target = output / (spec["name"] + ".blend")
    shutil.copy2(source, target)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    scene = bpy.context.scene
    if args.export_only:
        knots = [[scene.frame_start, scene.frame_start], [scene.frame_end, scene.frame_end]]
        recipe.validate_time_map(knots)
    assert scene.render.fps == 30 and abs(scene.render.fps_base - 1) < 1e-6
    assert (scene.frame_start, scene.frame_end) == tuple([knots[0][0], knots[-1][0]])
    rig = builder.find_rig()
    action = rig.animation_data.action
    action.name = spec["name"]
    forward = affine_map(knots)
    inverse = affine_map([(b, a) for a, b in knots])
    fcurves = curves(action)
    times = sorted(
        {i / 4 for i in range(int(knots[0][1]) * 4, int(knots[-1][1]) * 4 + 1)}
        | {forward(float(k.co.x)) for fc in fcurves for k in fc.keyframe_points}
    )
    before = sample(rig, [inverse(t) for t in times])
    added = 0 if args.export_only else sum(retime_curve(fc, knots) for fc in fcurves)
    for marker in scene.timeline_markers:
        marker.frame = round(forward(marker.frame))
    scene.frame_start, scene.frame_end = int(knots[0][1]), int(knots[-1][1])
    scene.frame_preview_start, scene.frame_preview_end = scene.frame_start, scene.frame_end
    action.use_frame_range = False
    after = sample(rig, times)
    error = max(matrix_error(a[n], b[n]) for a, b in zip(before, after) for n in a)
    assert error < 0.001, ("Corresponding poses changed", error)
    previews = builder.render_body_previews(
        rig,
        {"frame_start": scene.frame_start, "body_preview": spec.get("body_preview", {})},
        output,
    )
    scene.frame_set(scene.frame_start)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    builder.export_glb(rig, action, output)
    report = builder.validate_glb(output / (spec["name"] + ".glb"), spec["name"])
    report.update(
        source=str(source),
        source_sha256=digest,
        time_map=knots,
        maximum_pose_matrix_error=error,
        comparison_samples=len(times),
        added_scalar_curve_keys=added,
        previews=previews,
        in_game_verified=False,
    )
    (output / "recipe.resolved.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("GENERIC_RETIME_OK", json.dumps(report))


if __name__ == "__main__":
    main()
