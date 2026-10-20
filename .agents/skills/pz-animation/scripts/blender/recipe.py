"""Recipe validation and protected paths; standard library only."""

import hashlib
import json
import math
import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SKILL_ROOT.parents[2]
BUILD_ROOT = SKILL_ROOT / "work/output"
TEMPLATE = SKILL_ROOT / "assets/rig/PZ_HumanRigV4.blend"
LOCAL_CONFIG = REPO_ROOT / ".immersive-suicide.local.json"


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def valid_name(name):
    if not isinstance(name, str) or not re.fullmatch(r"Bob_[A-Za-z0-9_]+", name):
        raise ValueError("Use a Bob_ animation name with ASCII letters, digits and underscores")
    return name


# Find files relative to the game, skill, repository or recipe folder.
def resolve_path(value, parent):
    if value.startswith("game:"):
        if not LOCAL_CONFIG.is_file():
            raise ValueError(
                "Run initialize.ps1 -ProjectZomboidPath first; game: requires local configuration"
            )
        config = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8-sig"))
        if (
            not isinstance(config, dict)
            or type(config.get("schema")) is not int
            or config["schema"] != 1
        ):
            raise ValueError("Unsupported local project configuration schema")
        if set(config) - {"schema", "blender_path", "project_zomboid_path"}:
            raise ValueError("Unknown local project configuration key")
        root = config.get("project_zomboid_path")
        if not isinstance(root, str) or not root or not Path(root).is_absolute():
            raise ValueError("Configure an absolute project_zomboid_path with initialize.ps1")
        root = Path(root).resolve()
        if not (root / "media").is_dir():
            raise ValueError("project_zomboid_path must contain the game media/ directory")
        target = (root / value[5:]).resolve()
        if not target.is_relative_to(root):
            raise ValueError("game: path must remain within the configured game installation")
        return target
    if value.startswith("skill:"):
        return (SKILL_ROOT / value[6:]).resolve()
    if value.startswith("repo:"):
        return (REPO_ROOT / value[5:]).resolve()
    return (Path(parent) / value).resolve()


def read_recipe(path, seen=()):
    path = Path(path).resolve()
    if path in seen:
        raise ValueError("Cyclic recipe inheritance")
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(spec, dict):
        raise ValueError("Recipe must be a JSON object")
    if "extends" in spec:
        parent = read_recipe(resolve_path(spec["extends"], path.parent), (*seen, path))
        parent.update(spec)
        spec = parent
    # Use the recipe's folder to find preview files.
    # Files inherited from another recipe already have full paths.
    item = spec.get("held_item_preview")
    if item:
        for field in ("mesh_path", "texture_path"):
            if field in item:
                item[field] = str(resolve_path(item[field], path.parent))
    return spec


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def integer(value):
    if number(value) != int(value):
        raise ValueError("Authored frame numbers must be integers, not rounded floats")
    return int(value)


def vector(value, count):
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"Expected {count} vector components")
    for component in value:
        number(component)


def validate_template(spec):
    valid_name(spec.get("name"))
    if spec.get("schema") != 1 or spec.get("fps") != 30:
        raise ValueError("Template recipes require schema1 and fps30")
    start, end = integer(spec["frame_start"]), integer(spec["frame_end"])
    if start < 0 or start >= end:
        raise ValueError("Require 0 <= frame_start < frame_end")
    maximum = integer(spec.get("max_authored_keyframes_per_track", 16))
    if maximum < 1:
        raise ValueError("Key limit must be positive")
    for track in spec.get("tracks", []):
        if not track.get("bone", "").startswith("CTRL-"):
            raise ValueError("Author control bones, not deform bones")
        keys = track.get("keyframes", [])
        frames = [integer(key["frame"]) for key in keys]
        if not keys or frames != sorted(set(frames)) or not all(start <= f <= end for f in frames):
            raise ValueError("Track keys must be unique, sorted and within the clip range")
        if len(keys) > maximum or (len(keys) > 2 and len(keys) / (end - start + 1) > 0.25):
            raise ValueError("Authored movement must remain sparse")
        for key in keys:
            for field in ("location_offset", "rotation_degrees"):
                if field in key:
                    vector(key[field], 3)
            for field, allowed in [
                ("semantic_offset", {"up", "outward", "forward"}),
                ("semantic_rotation", {"roll", "pitch", "yaw"}),
            ]:
                if field in key:
                    if not isinstance(key[field], dict) or set(key[field]) - allowed:
                        raise ValueError(f"Unsupported {field} field")
                    for value in key[field].values():
                        number(value)
            if "elbow_height" in key:
                number(key["elbow_height"])
            if "prop_pose" in key:
                for field in ("blade_direction", "face_normal", "offset"):
                    vector(key["prop_pose"][field], 3)
    for control in spec.get("constant_controls", []):
        vector(control["rotation_quaternion"], 4)
        if sum(v * v for v in control["rotation_quaternion"]) < 1e-8:
            raise ValueError("Zero quaternion is not an orientation")
        if "location" in control:
            vector(control["location"], 3)
    for field in ("body_preview", "orientation_preview"):
        for item in spec.get(field, {}).get("frames", []):
            if not start <= integer(item["frame"]) <= end:
                raise ValueError("Preview frame outside clip")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", item["name"]):
                raise ValueError("Preview labels must not contain paths or punctuation")
    return spec


def validate_time_map(knots):
    if not isinstance(knots, list) or len(knots) < 2:
        raise ValueError("time_map needs at least two pairs")
    for pair in knots:
        vector(pair, 2)
    if not all(b[0] > a[0] and b[1] > a[1] for a, b in zip(knots, knots[1:])):
        raise ValueError("Both time_map axes must increase strictly")
    for pair in (knots[0], knots[-1]):
        for value in pair:
            if integer(value) < 0:
                raise ValueError("Negative clip endpoints are unsupported")


def output_path(name):
    return BUILD_ROOT / valid_name(name)


# Only allow edits to a verified working copy of the rig.
def require_template_copy(current, output, name):
    expected = output_path(name).resolve()
    current = Path(current).resolve()
    if Path(output).resolve() != expected or current != expected / (name + ".blend"):
        raise ValueError("Template builder requires a copied rig in its NEW work/output directory")
    if (
        current.samefile(TEMPLATE)
        or digest(current) != digest(TEMPLATE)
        or (expected / "validation.json").exists()
    ):
        raise ValueError(
            "Refusing to overwrite the rig, an existing animation, or an edited working copy"
        )
