import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from native_history import capture
from opposing_pass import finalize_sealed, measure
from test_opposing_pass import site


def vertices(station, lateral):
    return [[station + ds, lateral + dy, z]
            for ds in (-.8, .8) for dy in (-.6, .6) for z in (0, 1.5)]


class Adapter:
    def __init__(self, digest, gap=False, bad_vertex=False):
        self.digest = digest
        self.index = 0
        self.gap = gap
        self.bad_vertex = bad_vertex
    def source_attestation(self):
        return {"native_origin": True, "map_sha256": self.digest,
                "source_ref": "reviewed OpenDRIVE fixture"}
    def tick(self):
        i = self.index
        self.index += 1
        ego_vertices = vertices(-1+i, -1.7)
        if self.bad_vertex and i == 1:
            ego_vertices.pop()
        return {"native_frame": 100+i+(1 if self.gap and i == 1 else 0),
                "native_elapsed_s": 20+i/20,
                "ego": {"actor_id": "ego", "vertices_world_xyz_m": ego_vertices,
                        "velocity_world_xyz_mps": [6, 0, 0]},
                "other": {"actor_id": "other",
                          "vertices_world_xyz_m": vertices(1-i, 1.7),
                          "velocity_world_xyz_mps": [-6, 0, 0]}}


class NativeHistoryTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c125714-native-history-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        packet = site()
        packet["native_road_frame"] = {"source_id": "reviewed axis fixture",
                                       "origin_xyz_m": [0, 0, 0], "forward_xy": [1, 0]}
        packet["paved_boundary_source"] = "reviewed edge fixture"
        self.map_path = self.root / "map.json"
        self.map_path.write_text(json.dumps(packet) + "\n")
        self.digest = hashlib.sha256(self.map_path.read_bytes()).hexdigest()

    def test_project_seal_and_finalize_original_body_history(self):
        path = self.root / "trace.json"
        receipt = capture(Adapter(self.digest), self.map_path, self.digest,
                          "right_half", path, frames=3, diagnostic_fixture=True)
        self.assertTrue(receipt["diagnostic_fixture"])
        self.assertEqual(receipt["frame_count"], 3)
        trace = json.loads(path.read_text())
        self.assertEqual(trace["samples"][0]["native_frame"], 100)
        self.assertTrue(measure(trace)["right_of_other_all"])
        result = finalize_sealed(path, receipt["sha256"], self.root / "measurement.json")
        self.assertEqual(result["measurement"]["passing_frames"], [1])
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_rejects_gap_missing_body_and_short_production(self):
        with self.assertRaisesRegex(ValueError, "900 original frames"):
            capture(Adapter(self.digest), self.map_path, self.digest,
                    "right_half", self.root / "production.json", frames=3)
        with self.assertRaisesRegex(ValueError, "frame/time gap"):
            capture(Adapter(self.digest, gap=True), self.map_path, self.digest,
                    "right_half", self.root / "gap.json", frames=3, diagnostic_fixture=True)
        with self.assertRaisesRegex(ValueError, "eight original body vertices"):
            capture(Adapter(self.digest, bad_vertex=True), self.map_path, self.digest,
                    "right_half", self.root / "body.json", frames=3, diagnostic_fixture=True)

    def test_rejects_unsealed_map_and_false_attestation(self):
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            capture(Adapter(self.digest), self.map_path, "0"*64,
                    "right_half", self.root / "map.jsonl", frames=3, diagnostic_fixture=True)
        with self.assertRaisesRegex(ValueError, "attestation mismatch"):
            capture(Adapter("0"*64), self.map_path, self.digest,
                    "right_half", self.root / "attestation.json", frames=3,
                    diagnostic_fixture=True)


if __name__ == "__main__":
    unittest.main()
