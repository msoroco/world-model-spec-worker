"""Map custody and CPU-only exact entrypoint checks."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_runner import check_materialized_package, check_native_map, locate_repo_root, main, run_native
from parking_scene import build
from test_source_review import fixture


class RunnerTests(unittest.TestCase):
    def test_materialized_config_packet_must_match_selected_scene(self):
        with TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work") as tmp:
            packet, _ = fixture(tmp)
            scene = build(packet, tmp, "park_parallel_lawful")
            output = Path(tmp)
            (output / "construction.json").write_text(json.dumps({"case_id": scene["case_id"]}))
            (output / "scene.json").write_text(json.dumps(scene))
            (output / "runner.py").write_text("# CPU package fixture\n")
            config = {"selected_case_id": scene["case_id"], "reviewed_source_packet":
                {"path": "reviewed-context.json", "sha256": scene["source_packet_sha256"]}}
            (output / "config.json").write_text(json.dumps(config))
            check_materialized_package(output, scene)
            config["reviewed_source_packet"]["sha256"] = "0" * 64
            (output / "config.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "config source packet differs"):
                check_materialized_package(output, scene)

    def test_materialized_runner_finds_frozen_runtime_from_nested_attempt(self):
        repo = ROOT.parents[1]
        with TemporaryDirectory(dir=repo / ".runtime-work") as tmp:
            nested = Path(tmp) / "case" / "primary" / "offline"
            nested.mkdir(parents=True)
            script = nested / "parking_runner.py"
            script.write_text("# materialized bundle\n")
            self.assertEqual(locate_repo_root(script), repo)
        self.assertEqual(locate_repo_root(ROOT / "parking_runner.py"), repo)
        with self.assertRaisesRegex(ValueError, "cannot locate repository runtime"):
            locate_repo_root(Path("/no-such-materialized-runtime/runner.py"))

    def test_reviewed_native_map_readback_and_mismatch(self):
        with TemporaryDirectory() as tmp:
            packet_path, packet = fixture(tmp)
            road = "<OpenDRIVE><road id='1'/></OpenDRIVE>"
            packet["context"]["native_map_name"] = "TownTest"
            packet["context"]["native_opendrive_sha256"] = hashlib.sha256(road.encode()).hexdigest()
            packet_path.write_text(json.dumps(packet))
            world = SimpleNamespace(get_map=lambda: SimpleNamespace(name="TownTest",
                                                                     to_opendrive=lambda: road))
            self.assertEqual(check_native_map(world, packet_path, tmp)["native_map_name"],
                             "TownTest")
            other = SimpleNamespace(get_map=lambda: SimpleNamespace(name="OtherTown",
                                                                     to_opendrive=lambda: road))
            with self.assertRaisesRegex(ValueError, "readback differs"):
                check_native_map(other, packet_path, tmp)
            packet["context"].pop("native_opendrive_sha256")
            packet_path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "map name and OpenDRIVE hash required"):
                check_native_map(world, packet_path, tmp)

    def test_cpu_check_never_imports_carla_or_writes_attempt(self):
        with TemporaryDirectory() as tmp:
            packet, _ = fixture(tmp)
            argv = ["parking_runner.py", "--packet", str(packet), "--source-root", tmp,
                    "--case", "park_parallel_lawful", "--check"]
            with patch.object(sys, "argv", argv), patch("builtins.print") as shown:
                main()
            self.assertEqual(json.loads(shown.call_args.args[0])["case_id"],
                             ROOT.name + "__park_parallel_lawful")
            with self.assertRaisesRegex(ValueError, "materialized attempt under"):
                run_native(packet, tmp, "park_parallel_lawful", Path(tmp) / "not-created")


if __name__ == "__main__":
    unittest.main()
