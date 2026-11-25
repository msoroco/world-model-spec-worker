import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_source_adapter import ReviewedAdapter
from native_capture import capture, CAMERAS


class World:
    def get_map(self):
        return self

    def to_opendrive(self):
        return "reviewed-crest-map"


class Delegate:
    def __init__(self, context):
        self.context = context
        self.begun = False
        self.closed = False
        self.frame = -1

    def begin(self, case_id):
        self.begun = True
        return self.context

    def close(self):
        self.closed = True

    def tick(self):
        self.frame += 1
        return self.frame

    def sample(self, frame):
        return ({"frame": frame, "timestamp_s": frame / 20,
                 "ego_body_corners_signed_m": [-1, -.5, .1, .2],
                 "opposing_body_distance_m": 25,
                 "ego_source_ref": "fixture ego", "opposing_source_ref": "fixture other"},
                {"frame": frame, "body_corner_ray_hits": [True] * 4,
                 "ray_source_ref": "fixture rays"})

    def camera_frames(self, frame):
        return {name: frame for name in CAMERAS}

    def write_camera_video(self, camera, path):
        path.write_bytes(("diagnostic " + camera).encode())


class SourceAdapterTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT.parents[1] / '.runtime-work' / 'c104084-source-facts-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / "attempt"
        self.output.mkdir()

    def fixture(self, suffix):
        case_id = "testing__C104084__NRS-484B-213-2a__motor_vehicle_driver__" + suffix
        one_way = suffix == "left_one_way_obstructed"
        kinds = ("highway", "center_reference", "one_way_authority" if one_way else "opposing_lane")
        sources = {}
        hashes = {}
        facts = {"highway": "public_highway",
                 "center_reference": "center_reference_present",
                 "opposing_lane": "opposing_direction_present",
                 "one_way_authority": "one_way_designation"}
        for kind in kinds:
            data = json.dumps({"source_kind": kind, "source_citation": "fixture citation",
                               "case_id": case_id,
                               "map_opendrive_sha256": hashlib.sha256(b"reviewed-crest-map").hexdigest(),
                               facts[kind]: True}).encode()
            (self.root / (kind + ".json")).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            sources[kind] = {"path": kind + ".json", "sha256": digest,
                             "reviewer": "fixture reviewer", "source_citation": "fixture citation"}
            hashes[kind] = digest
        packet = {"case_id": case_id, "law_id": "NRS-484B-213-2a",
                  "reviewer": "fixture reviewer", "source_citation": "fixture citation",
                  "map_opendrive_sha256": hashlib.sha256(b"reviewed-crest-map").hexdigest(),
                  "sources": sources}
        packet_path = self.root / "packet.json"
        packet_path.write_text(json.dumps(packet))
        context = {"case_id": case_id, "law_id": packet["law_id"],
                   "highway_source_ref": hashes["highway"],
                   "center_reference_source_ref": hashes["center_reference"],
                   "lane_allocation": "one_way" if one_way else "two_way"}
        if one_way:
            context["one_way_authority"] = {"sha256": hashes["one_way_authority"],
                                            "source_ref": "fixture citation"}
        else:
            context["opposing_lane_source_ref"] = hashes["opposing_lane"]
        delegate = Delegate(context)
        adapter = ReviewedAdapter(delegate, packet_path=packet_path,
                                  source_root=self.root, output=self.output, world=World())
        return adapter, delegate, packet_path, case_id

    def test_two_way_source_join(self):
        adapter, delegate, _, case_id = self.fixture("left_crest_obstructed")
        self.assertEqual(adapter.begin(case_id)["lane_allocation"], "two_way")
        self.assertTrue(delegate.begun)

    def test_source_gate_to_original_capture(self):
        adapter, delegate, _, case_id = self.fixture("left_crest_obstructed")
        result = capture(adapter, self.output, assignment_id=ROOT.name,
                         case_id=case_id, frames=3)
        self.assertEqual(result["frame_count"], 3)
        self.assertTrue(delegate.closed)
        self.assertIn("frames.jsonl", result["source_sha256"])
        self.assertIn("reviewed-highway.json", result["source_sha256"])
        self.assertEqual((self.output / "reviewed-highway.json").read_bytes(),
                         (self.root / "highway.json").read_bytes())

    def test_one_way_authority_retained(self):
        adapter, _, _, case_id = self.fixture("left_one_way_obstructed")
        adapter.begin(case_id)
        self.assertEqual((self.output / "one-way-authority.json").read_bytes(),
                         (self.root / "one_way_authority.json").read_bytes())

    def test_tampered_source_rejected_before_delegate(self):
        adapter, delegate, _, case_id = self.fixture("left_crest_obstructed")
        (self.root / "highway.json").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            adapter.begin(case_id)
        self.assertFalse(delegate.begun)

    def test_changed_live_map_rejected_before_delegate(self):
        adapter, delegate, packet_path, case_id = self.fixture("left_crest_obstructed")
        packet = json.loads(packet_path.read_text())
        packet["map_opendrive_sha256"] = "0" * 64
        packet_path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "map hash mismatch"):
            adapter.begin(case_id)
        self.assertFalse(delegate.begun)

    def test_rehashed_wrong_native_context_rejected(self):
        adapter, delegate, _, case_id = self.fixture("left_crest_obstructed")
        delegate.context["opposing_lane_source_ref"] = "wrong"
        with self.assertRaisesRegex(ValueError, "opposing-lane context"):
            adapter.begin(case_id)

    def test_rehashed_contradictory_source_fact_rejected(self):
        adapter, delegate, packet_path, case_id = self.fixture("left_crest_obstructed")
        source = self.root / 'opposing_lane.json'
        document = json.loads(source.read_text())
        document['opposing_direction_present'] = False
        source.write_text(json.dumps(document))
        packet = json.loads(packet_path.read_text())
        packet['sources']['opposing_lane']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        packet_path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, 'source fact missing'):
            adapter.begin(case_id)
        self.assertFalse(delegate.begun)

    def test_rehashed_foreign_case_source_rejected(self):
        adapter, delegate, packet_path, case_id = self.fixture("left_one_way_obstructed")
        source = self.root / 'one_way_authority.json'
        document = json.loads(source.read_text())
        document['case_id'] = 'another-case'
        source.write_text(json.dumps(document))
        packet = json.loads(packet_path.read_text())
        packet['sources']['one_way_authority']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        packet_path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, 'source claim mismatch'):
            adapter.begin(case_id)
        self.assertFalse(delegate.begun)


if __name__ == "__main__":
    unittest.main()
