"""Dependency-free contract tests. Run with Python or Blender --python."""

import ast
import copy
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[2]
sys.path.insert(0, str(SKILL / "scripts/blender"))
import recipe


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.spec = recipe.read_recipe(SKILL / "assets/specs/hand-gesture.json")

    def test_curated_asset_hashes(self):
        registry = json.loads((SKILL / "assets/references.json").read_text())
        for item in registry["reference_assets"]:
            path = recipe.resolve_path(item["path"], SKILL)
            self.assertEqual(recipe.digest(path), item["sha256"], str(path))

    def test_no_unregistered_binary_assets(self):
        registry = json.loads((SKILL / "assets/references.json").read_text())
        expected = {recipe.resolve_path(x["path"], SKILL) for x in registry["reference_assets"]}
        actual = {
            p.resolve()
            for p in (SKILL / "assets").rglob("*")
            if p.is_file() and p.suffix in {".blend", ".glb"}
        }
        self.assertEqual(actual, expected)

    def test_example_guides_and_developer_manifest(self):
        registry = json.loads((SKILL / "assets/references.json").read_text())
        manifest = json.loads((ROOT / "developer-assets.json").read_text())
        by_path = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
        guides = registry["example_guides"]
        for group, guide in guides.items():
            self.assertTrue(recipe.resolve_path(guide, SKILL).is_file())
            self.assertTrue((SKILL / "assets/examples" / group).is_dir())
        for entry in registry["reference_assets"]:
            asset = recipe.resolve_path(entry["path"], SKILL)
            self.assertEqual(by_path[asset.relative_to(ROOT).as_posix()], entry["sha256"])
            if "example" in entry:
                self.assertIn(entry["example"], guides)
                self.assertTrue(asset.is_relative_to(SKILL / "assets/examples" / entry["example"]))
        self.assertFalse(any(path.startswith("Contents/") for path in by_path))

    def test_valid_starter(self):
        self.assertIs(recipe.validate_template(self.spec), self.spec)

    def test_game_path_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "media").mkdir()
            config = root / "local.json"
            with patch.object(recipe, "LOCAL_CONFIG", config):
                with self.assertRaisesRegex(ValueError, "initialize"):
                    recipe.resolve_path("game:media/Knife.X", root)
                config.write_text(json.dumps({"schema": 1, "project_zomboid_path": str(root)}))
                self.assertEqual(
                    recipe.resolve_path("game:media/Knife.X", root), root / "media/Knife.X"
                )
                for path in ["game:../escape", "game:" + str(root.parent / "escape")]:
                    with self.assertRaises(ValueError):
                        recipe.resolve_path(path, root)
                for value in [None, "relative", str(root / "absent")]:
                    config.write_text(json.dumps({"schema": 1, "project_zomboid_path": value}))
                    with self.assertRaises(ValueError):
                        recipe.resolve_path("game:media/Knife.X", root)

    def test_preview_paths_are_recipe_relative(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "preview.json"
            source.write_text(
                json.dumps(
                    {"held_item_preview": {"mesh_path": "Knife.X", "texture_path": "Knife.png"}}
                )
            )
            item = recipe.read_recipe(source)["held_item_preview"]
            self.assertEqual(Path(item["mesh_path"]), root / "Knife.X")
            self.assertEqual(Path(item["texture_path"]), root / "Knife.png")

    def test_unsafe_names(self):
        for name in ["../Bob_X", "Bob_a/b", "Bob_ÃƒÂ¤", "Bob_X.glb", "bob_x", ""]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                recipe.valid_name(name)

    def test_fractional_and_out_of_range_frames(self):
        for value in [1.5, -1, 999, True]:
            spec = copy.deepcopy(self.spec)
            spec["tracks"][0]["keyframes"][1]["frame"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                recipe.validate_template(spec)

    def test_duplicate_and_unsorted_keys(self):
        for value in [0, 60]:
            spec = copy.deepcopy(self.spec)
            spec["tracks"][0]["keyframes"][1]["frame"] = value
            with self.assertRaises(ValueError):
                recipe.validate_template(spec)

    def test_nonfinite_bad_vectors_and_semantic_typos(self):
        for change in [
            {"semantic_offset": {"up": float("nan")}},
            {"semantic_offset": {"up": float("inf")}},
            {"semantic_offset": {"upp": 2}},
            {"rotation_degrees": [1, 2]},
        ]:
            spec = copy.deepcopy(self.spec)
            spec["tracks"][0]["keyframes"][1].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                recipe.validate_template(spec)

    def test_dense_motion_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["tracks"][0]["keyframes"] = [{"frame": f, "semantic_offset": {}} for f in range(73)]
        with self.assertRaises(ValueError):
            recipe.validate_template(spec)

    def test_preview_path_escape_rejected(self):
        self.spec["body_preview"]["frames"][0]["name"] = "../../outside"
        with self.assertRaises(ValueError):
            recipe.validate_template(self.spec)

    def test_cyclic_inheritance_and_bom(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.json", Path(folder) / "b.json"
            a.write_text(json.dumps({"extends": "b.json"}), encoding="utf-8-sig")
            b.write_text(json.dumps({"extends": "a.json"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Cyclic"):
                recipe.read_recipe(a)
            a.write_text(json.dumps(self.spec), encoding="utf-8-sig")
            recipe.validate_template(recipe.read_recipe(a))

    def test_time_maps(self):
        recipe.validate_time_map([[0, 0], [30, 20], [60, 50]])
        for knots in [
            [],
            [[0, 0]],
            [[0, 0], [30, 0]],
            [[0, 0], [0, 10]],
            [[0, 0], [20.5, 30]],
            [[0, 0], [30, float("nan")]],
        ]:
            with self.subTest(knots=knots), self.assertRaises(ValueError):
                recipe.validate_time_map(knots)

    def test_template_copy_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            template = folder / "rig.blend"
            template.write_bytes(b"template-test-data")
            output = folder / "output" / "Bob_Test"
            output.mkdir(parents=True)
            working = output / "Bob_Test.blend"
            shutil.copyfile(template, working)
            with patch.object(recipe, "BUILD_ROOT", folder / "output"), patch.object(
                recipe, "TEMPLATE", template
            ):
                recipe.require_template_copy(working, output, "Bob_Test")
                with self.assertRaises(ValueError):
                    recipe.require_template_copy(template, output, "Bob_Test")
                working.write_bytes(b"edited-test-data")
                with self.assertRaises(ValueError):
                    recipe.require_template_copy(working, output, "Bob_Test")
                self.assertEqual(template.read_bytes(), b"template-test-data")

    def test_module_syntax_and_local_imports(self):
        for path in (SKILL / "scripts").rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), str(path))
        for path in (SKILL / "assets/examples").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            ast.parse(text, str(path))
            self.assertIn("Construction reference only", text)
        for path in (SKILL / "scripts/blender").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(
                        node.module,
                        {
                            "continue_manual_animation",
                            "polish_manual_animation",
                            "retime_animation",
                            "append_fall",
                            "append_kneel",
                            "append_recovery",
                            "repair_timing_handles",
                        },
                    )

    def test_skill_and_reference_links(self):
        path = SKILL / "SKILL.md"
        text = path.read_text()
        front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        self.assertIsNotNone(front)
        fields = dict(line.split(": ", 1) for line in front[1].splitlines())
        self.assertEqual(fields["name"], "pz-animation")
        self.assertTrue(30 < len(fields["description"]) < 1025)
        for path in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" not in target:
                    self.assertTrue((path.parent / target.split("#")[0]).exists(), (path, target))

    def test_sources_only_and_no_obsolete_scaffolding(self):
        # Keep the tracked placeholder and optional Blender backups out of the source check.
        files = [
            p
            for p in (ROOT / "animation").iterdir()
            if p.name != ".gitkeep" and not (p.is_file() and p.suffix == ".blend1")
        ]
        self.assertTrue(files and all(p.is_file() and p.suffix == ".blend" for p in files))
        self.assertFalse((SKILL / "references/history").exists())
        self.assertFalse((SKILL / "scripts/inventory-animations.py").exists())
        self.assertFalse((SKILL / "scripts/build-animation.ps1").exists())


if __name__ == "__main__":
    unittest.main(argv=[__file__])
