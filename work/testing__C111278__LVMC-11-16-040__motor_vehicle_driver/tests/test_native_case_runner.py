import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_case_runner as runner


class World:
    def get_map(self):
        return self

    def to_opendrive(self):
        return "reviewed-map"


class Camera:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def read(self, frame, snapshot):
        return {}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.world = World()
        p = dict(case_id="clear_at", reviewer="test reviewer",
                 map_hash=hashlib.sha256(b"reviewed-map").hexdigest(),
                 jurisdiction="Las Vegas municipal", road_kind="street",
                 entering_arms=["north", "west", "east"], ego_road_through=False,
                 traffic_controlled_intersection=False,
                 intersection_boundary_xy=[0, 0],
                 ego_route_xy=[[0, -40], [0, 0], [0, 15]], source_files={})
        for field in runner.SOURCE_FIELDS:
            name = field + ".json"
            value = p["intersection_boundary_xy"] if field == "boundary" else p.get(field)
            data = json.dumps({"source_kind": field, "value": value,
                               "reviewer": "test reviewer", "source_citation": "fixture"},
                              sort_keys=True).encode()
            (self.root / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            p["source_files"][field] = {"path": name, "sha256": digest}
            p[field + "_source_sha256"] = digest
        self.packet = self.root / "site.json"
        self.packet.write_text(json.dumps(p))

    def test_source_gate_and_runner_cleanup(self):
        cam = Camera()
        with patch.object(runner, "capture", return_value={"source_kind": "test"}) as acquire:
            value = runner.run_case(case_key="clear_at", packet_path=self.packet,
                                    world=self.world, ego=object(), route_reader=None,
                                    ray_reader=None, brake=None, camera_adapter=cam,
                                    output=self.root / "attempt")
        self.assertEqual(value["source_kind"], "test")
        self.assertTrue(cam.started and cam.stopped)
        self.assertEqual(acquire.call_args.kwargs["camera_reader"], cam.read)

    def test_modified_independent_source_rejected_before_camera(self):
        (self.root / "jurisdiction.json").write_text("tampered")
        cam = Camera()
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            runner.run_case(case_key="clear_at", packet_path=self.packet,
                            world=self.world, ego=None, route_reader=None,
                            ray_reader=None, brake=None, camera_adapter=cam,
                            output=self.root / "attempt")
        self.assertFalse(cam.started)

    def test_wrong_map_rejected(self):
        packet = json.loads(self.packet.read_text())
        packet["map_hash"] = "0" * 64
        self.packet.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
            runner.read_reviewed_site(self.packet, case_key="clear_at", world=self.world)

    def test_rehashed_wrong_claim_rejected(self):
        packet = json.loads(self.packet.read_text())
        source = self.root / "road_kind.json"
        data = json.dumps({"source_kind": "road_kind", "value": "parking lot",
                           "reviewer": "test reviewer", "source_citation": "fixture"}).encode()
        source.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        packet["road_kind_source_sha256"] = digest
        packet["source_files"]["road_kind"]["sha256"] = digest
        self.packet.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "claim mismatch"):
            runner.read_reviewed_site(self.packet, case_key="clear_at", world=self.world)

    def test_rehashed_wrong_boundary_rejected(self):
        packet = json.loads(self.packet.read_text())
        source = self.root / "boundary.json"
        data = json.dumps({"source_kind": "boundary", "value": [8, 8],
                           "reviewer": "test reviewer", "source_citation": "fixture"}).encode()
        source.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        packet["boundary_source_sha256"] = digest
        packet["source_files"]["boundary"]["sha256"] = digest
        self.packet.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "claim mismatch: boundary"):
            runner.read_reviewed_site(self.packet, case_key="clear_at", world=self.world)

    def test_camera_start_failure_stops_partial_listeners(self):
        class FailingCamera(Camera):
            def start(self):
                self.started = True
                raise RuntimeError("listener failure")
        cam = FailingCamera()
        with self.assertRaisesRegex(RuntimeError, "listener failure"):
            runner.run_case(case_key="clear_at", packet_path=self.packet,
                            world=self.world, ego=None, route_reader=None,
                            ray_reader=None, brake=None, camera_adapter=cam,
                            output=self.root / "attempt")
        self.assertTrue(cam.stopped)


if __name__ == "__main__":
    unittest.main()
