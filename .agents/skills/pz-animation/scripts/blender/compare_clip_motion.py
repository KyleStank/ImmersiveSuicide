"""Compare all sampled animation channels in two GLBs, ignoring clip names.

Run with Blender --background --python this_file -- reference.glb candidate.glb.
Reads only; no Blender scene or file is changed.
"""

import json
import struct
import sys
from pathlib import Path


def read_glb(path):
    data = Path(path).read_bytes()
    magic, version, size = struct.unpack_from("<4sII", data)
    assert magic == b"glTF" and version == 2 and size == len(data)
    chunks = {}
    offset = 12
    while offset < len(data):
        length, kind = struct.unpack_from("<I4s", data, offset)
        chunks[kind] = data[offset + 8 : offset + 8 + length]
        offset += length + 8
    return json.loads(chunks[b"JSON"]), chunks[b"BIN\x00"]


def accessor_values(doc, binary, index):
    acc = doc["accessors"][index]
    assert acc["componentType"] == 5126 and "sparse" not in acc
    width = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[acc["type"]]
    view = doc["bufferViews"][acc["bufferView"]]
    stride = view.get("byteStride", width * 4)
    offset = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    return tuple(
        value
        for row in range(acc["count"])
        for value in struct.unpack_from("<" + "f" * width, binary, offset + row * stride)
    )


# Read the animation values so the two exports can be compared.
def channels(doc, binary):
    assert len(doc["animations"]) == 1
    anim = doc["animations"][0]
    result = {}
    for channel in anim["channels"]:
        target = channel["target"]
        key = (doc["nodes"][target["node"]]["name"], target["path"])
        sampler = anim["samplers"][channel["sampler"]]
        result[key] = (
            sampler.get("interpolation", "LINEAR"),
            accessor_values(doc, binary, sampler["input"]),
            accessor_values(doc, binary, sampler["output"]),
        )
    return result


paths = sys.argv[sys.argv.index("--") + 1 :]
allow_prop_change = "--allow-right-prop-change" in paths
allow_finger_change = "--allow-right-finger-change" in paths
paths = [
    path
    for path in paths
    if path not in {"--allow-right-prop-change", "--allow-right-finger-change"}
]
assert len(paths) == 2, "Supply reference.glb and candidate.glb"
reference = channels(*read_glb(paths[0]))
candidate_doc, candidate_binary = read_glb(paths[1])
candidate = channels(candidate_doc, candidate_binary)
assert reference.keys() == candidate.keys(), "Exported animation channels changed"
assert ("Bip01_Prop1", "rotation") in candidate, "Missing right prop rotation"
assert ("Bip01_Prop1", "translation") in candidate, "Missing right prop position"
assert not any("PREVIEW-" in node.get("name", "") for node in candidate_doc["nodes"])
maximum_error = 0.0
changed_prop_channels = []
changed_finger_channels = []
for key, (interpolation, times, values) in reference.items():
    other_interpolation, other_times, other_values = candidate[key]
    assert interpolation == other_interpolation and times == other_times, key
    assert len(values) == len(other_values), key
    error = max(abs(a - b) for a, b in zip(values, other_values))
    if allow_finger_change and key[0] in {
        "Bip01_R_Finger0",
        "Bip01_R_Finger0Nub",
        "Bip01_R_Finger1",
        "Bip01_R_Finger1Nub",
    }:
        if error > 1e-6:
            changed_finger_channels.append(key)
        continue
    if allow_prop_change and key[0] in {"Bip01_Prop1", "Bip01_Prop1_end"}:
        if error > 1e-6:
            changed_prop_channels.append(key)
        continue
    maximum_error = max(maximum_error, error)
    assert error <= 1e-6, (key, error)
print(
    json.dumps(
        {
            "unchanged_channels_match_reference": True,
            "compared_channels": len(candidate),
            "maximum_component_error": maximum_error,
            "allowed_changed_prop_channels": changed_prop_channels,
            "allowed_changed_finger_channels": changed_finger_channels,
            "right_prop_position_and_rotation_exported": True,
            "preview_mesh_excluded": True,
        },
        indent=2,
    )
)
