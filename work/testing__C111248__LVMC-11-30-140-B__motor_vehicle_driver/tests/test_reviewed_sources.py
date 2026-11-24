import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("blind_reviewed_sources", ROOT / "reviewed_sources.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
capture_spec = importlib.util.spec_from_file_location("blind_native_reviewed_test", ROOT / "native_capture.py")
native = importlib.util.module_from_spec(capture_spec)
sys.modules[capture_spec.name] = native
capture_spec.loader.exec_module(native)


class ReviewedSourcesTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c111248-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def packet(self):
        original_att = self.write("original-att.json", {"reviewed_fact": "fixture blindness basis"})
        original_cue = self.write("original-cue.json", {"reviewed_fact": "fixture carried white cane"})
        att = self.write("att.json", {"person_actor_id": 5, "basis": "partially_blind", "issuer": "fixture issuer",
                                      "source_sha256": original_att["sha256"], "original_source": original_att})
        cue = self.write("cue.json", {"person_actor_id": 5, "cue": "white_cane", "observation": "actually_carried",
                                      "observer_source": "fixture observer", "source_sha256": original_cue["sha256"],
                                      "original_source": original_cue})
        route = [{"map_id": "TownFixture", "x": x, "y": 0, "road_id": 1, "lane_id": 1} for x in (0, 10)]
        mapped = self.write("map.json", {"reviewed_from": "original_native_map", "reviewer": "fixture reviewer",
                                         "map_id": "TownFixture", "route_waypoints": route,
                                         "pedestrian_pose": {"map_id": "TownFixture", "x": 10, "y": 2, "ground_z": 0},
                                         "driver_actor_id": 4, "pedestrian_actor_id": 5})
        packet = {"assignment_id": ROOT.name, "case_id": "white_full_stop_wait",
                  "reviewed_map_route": mapped, "blindness_attestation": att, "carried_cue": cue}
        self.write("packet.json", packet)
        return packet

    def test_plan_binds_five_distinct_sources(self):
        self.packet()
        plan = module.prepare(self.root / "packet.json")
        self.assertEqual(plan["pedestrian_actor_id"], 5)
        self.assertEqual(len(plan["reviewed_source_bindings"]), 6)
        self.assertFalse(plan["physical_acceptance_claimed"])

    def test_materialized_bundle_folder_preserves_source_identity(self):
        self.packet()
        bundle = self.root / "offline-materialization"
        bundle.mkdir()
        for name in ("blind_encounter.py", "reviewed_sources.py"):
            (bundle / name).write_bytes((ROOT / name).read_bytes())
        spec = importlib.util.spec_from_file_location("materialized_reviewed_sources", bundle / "reviewed_sources.py")
        materialized = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = materialized
        spec.loader.exec_module(materialized)
        self.assertEqual(materialized.ASSIGNMENT_ID, ROOT.name)
        self.assertEqual(materialized.prepare(self.root / "packet.json")["pedestrian_actor_id"], 5)

    def test_rejects_changed_map_and_wrong_cue(self):
        packet = self.packet()
        (self.root / "map.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            module.prepare(self.root / "packet.json")
        packet["reviewed_map_route"]["sha256"] = hashlib.sha256((self.root / "map.json").read_bytes()).hexdigest()
        self.write("packet.json", packet)
        with self.assertRaisesRegex(ValueError, "original Native map review"):
            module.prepare(self.root / "packet.json")

    def test_rejects_source_provenance_and_escaping_path(self):
        packet = self.packet()
        original = self.root / "original-att.json"
        original.write_text('{"changed": true}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            module.prepare(self.root / "packet.json")
        packet["reviewed_map_route"]["path"] = "../escape.json"
        self.write("packet.json", packet)
        with self.assertRaisesRegex(ValueError, "escaping"):
            module.prepare(self.root / "packet.json")

    def test_capture_entrypoint_requires_packet_and_seals_map_binding(self):
        self.packet()
        (self.root / "attempt").mkdir()
        with patch.object(native, "capture", return_value={"case_id": "white_full_stop_wait"}) as run:
            result = native.capture_reviewed(object(), "white_full_stop_wait", self.root / "attempt",
                                             source_packet=self.root / "packet.json")
        self.assertEqual(result["reviewed_map_id"], "TownFixture")
        self.assertEqual(len(result["reviewed_source_bindings"]), 6)
        self.assertEqual(module.prepare(self.root / "attempt/reviewed-source/packet.json")["reviewed_source_bindings"],
                         result["reviewed_source_bindings"])
        self.assertEqual(result["reviewed_source_packet"]["sha256"],
                         hashlib.sha256((self.root / "packet.json").read_bytes()).hexdigest())
        self.assertEqual(run.call_args.kwargs["attestation"], self.root / "att.json")
        with self.assertRaisesRegex(ValueError, "exact case mismatch"):
            native.capture_reviewed(object(), "white_roll_through", self.root / "other",
                                    source_packet=self.root / "packet.json")


if __name__ == "__main__":
    unittest.main()
