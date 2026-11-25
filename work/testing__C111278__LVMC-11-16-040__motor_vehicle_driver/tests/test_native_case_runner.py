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

    def test_blocked_case_requires_independent_occluder_claim(self):
        packet = json.loads(self.packet.read_text())
        packet["case_id"] = "blocked_at"
        packet["occluder_sites"] = {"west_building": {
            "source_sha256": "a" * 64, "blueprint_id": "static.prop.test",
            "transform": {"x": -5, "y": 2}, "affected_arm": "west"}}
        self.packet.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "placement source missing"):
            runner.read_reviewed_site(self.packet, case_key="blocked_at", world=self.world)
        doc = {"source_kind": "occluder_sites", "reviewer": "test reviewer",
               "source_citation": "synthetic fixture only", "value": packet["occluder_sites"]}
        raw = json.dumps(doc, sort_keys=True).encode()
        (self.root / "occluder.json").write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        packet["source_files"]["occluder_sites"] = {"path": "occluder.json", "sha256": digest}
        packet["occluder_sites_source_sha256"] = digest
        self.packet.write_text(json.dumps(packet))
        self.assertEqual(runner.read_reviewed_site(
            self.packet, case_key="blocked_at", world=self.world)["case_id"], "blocked_at")

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

    def test_reviewed_route_reader_is_bound_before_acquisition(self):
        packet = json.loads(self.packet.read_text())
        route = {"source_kind": "ego_route_geometry", "reviewer": "test reviewer",
                 "source_citation": "fixture only", "route_xy": packet["ego_route_xy"],
                 "intersection_boundary_xy": [0, 0], "traversal_exit_xy": [0, 10]}
        raw = json.dumps(route, sort_keys=True).encode()
        (self.root / "route.json").write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        packet["ego_route_xy_source_sha256"] = digest
        packet["source_files"]["ego_route_geometry"] = {"path": "route.json", "sha256": digest}
        self.packet.write_text(json.dumps(packet))
        with patch.object(runner, "run_case", return_value={"bound": True}) as acquire:
            receipt = runner.run_case_with_reviewed_route(
                case_key="clear_at", packet_path=self.packet, world=self.world,
                ego=object(), ray_reader=lambda *args: {}, brake=None,
                camera_adapter=Camera(), output=self.root / "attempt")
        self.assertEqual(receipt, {"bound": True})
        self.assertEqual(type(acquire.call_args.kwargs["route_reader"]).__name__,
                         "ReviewedRouteReader")
        arm_geometry = {"source_kind": "arm_sight_geometry", "reviewer": "test reviewer",
                        "source_citation": "fixture only", "entering_arms": packet["entering_arms"],
                        "arm_geometry": {arm: {"sampled_extent_m": 31,
                                               "intersection_xyz": [0, 0, 1.4],
                                               "traffic_corridor_xyz": [
                                                   {"station_m": i * 30.48 / 8,
                                                    "xyz": [0, i * 31 / 8, 1.4]}
                                                   for i in range(9)]}
                                         for arm in packet["entering_arms"]}}
        ray_raw = json.dumps(arm_geometry, sort_keys=True).encode()
        (self.root / "arm-geometry.json").write_bytes(ray_raw)
        ray_digest = hashlib.sha256(ray_raw).hexdigest()
        packet["arm_sight_geometry_source_sha256"] = ray_digest
        packet["source_files"]["arm_sight_geometry"] = {
            "path": "arm-geometry.json", "sha256": ray_digest}
        self.packet.write_text(json.dumps(packet))
        with patch.object(runner, "run_case", return_value={"bound": True}) as acquire:
            runner.run_case_with_reviewed_route(
                case_key="clear_at", packet_path=self.packet, world=self.world,
                ego=object(), ray_reader=None, brake=None, camera_adapter=Camera(),
                output=self.root / "attempt", traffic_reader=lambda *args: {},
                location_factory=lambda *args: object())
        self.assertEqual(type(acquire.call_args.kwargs["ray_reader"]).__name__,
                         "ReviewedRayReader")
        (self.root / "route.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "inventory hash mismatch"):
            runner.run_case_with_reviewed_route(
                case_key="clear_at", packet_path=self.packet, world=self.world,
                ego=object(), ray_reader=lambda *args: {}, brake=None,
                camera_adapter=Camera(), output=self.root / "attempt")


if __name__ == "__main__":
    unittest.main()
