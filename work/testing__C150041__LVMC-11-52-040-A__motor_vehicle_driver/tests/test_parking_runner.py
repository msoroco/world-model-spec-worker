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
from parking_runner import check_native_map, main, run_native
from test_source_review import fixture


class RunnerTests(unittest.TestCase):
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
            with self.assertRaisesRegex(ValueError, "fresh attempt under"):
                run_native(packet, tmp, "park_parallel_lawful", tmp)


if __name__ == "__main__":
    unittest.main()
