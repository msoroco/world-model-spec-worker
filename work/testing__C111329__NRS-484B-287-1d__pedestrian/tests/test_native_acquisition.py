import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_crossing import digest
from native_acquisition import acquire, save
from saved_measurement import measure_acquisition


def site():
    return {"map_name": "diagnostic-map", "map_sha256": "a" * 64,
            "survey_source": "diagnostic measured site", "corners": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "intersection_polygon": [[-1, -1], [11, -1], [11, 11], [-1, 11]],
            "devices": [{"id": "d1", "official_source": "diagnostic inventory",
                         "instruction_source": "diagnostic instruction", "pedestrian_governance": "diagonal",
                         "state": "permissive"}]}


class Adapter:
    is_diagnostic = True

    def __init__(self, problem=None):
        self.problem, self.n, self.cleaned = problem, -1, False

    def spawn_walker(self, bp, xy): return {"id": 7}
    def drive_walker_route(self, actor, path): self.route = path
    def walker_id(self, actor): return 8 if self.problem == "identity" and self.n == 1 else 7
    def walker_xy(self, actor): return self.route[-1] if self.n >= 2 else self.route[0]
    def tick(self):
        self.n += 1
        f = self.n + (1 if self.problem == "frame" and self.n >= 1 else 0)
        return {"original_frame": f, "elapsed_seconds": self.n / 20}
    def read_devices(self):
        d = dict(site()["devices"][0])
        if self.problem == "provenance" and self.n == 1: d["official_source"] = "different"
        return [d]
    def camera_frames(self):
        frames = {name: self.n for name in ("overview", "approach", "reference_corner", "driver_reference")}
        if self.problem == "camera" and self.n == 1: frames["approach"] += 1
        return frames
    def stop_walker(self, actor): self.cleaned = True
    def destroy_actor(self, actor): self.cleaned = True


class NativeAcquisitionTests(unittest.TestCase):
    def test_source_bound_continuous_readbacks_and_seal(self):
        s = site()
        packet = acquire(Adapter(), site=s, site_sha256=digest(s), case_id="diagnostic-exact-case",
                         route_kind="opposite", authorization=True,
                         blueprint_id="walker.pedestrian.0001", frames=3)
        self.assertEqual(packet["frame_count"], 3)
        self.assertEqual([r["original_frame"] for r in packet["rows"]], [0, 1, 2])
        self.assertTrue(packet["diagnostic"])
        measured = measure_acquisition(s, packet, case_id="diagnostic-exact-case",
                                       route_kind="opposite", authorization=True,
                                       expected_frames=3, allow_diagnostic=True)
        self.assertTrue(measured["camera_frames_verified"])
        self.assertTrue(measured["authorization_observed_during_inside"])
        with self.assertRaisesRegex(ValueError, "diagnostic"):
            measure_acquisition(s, packet, case_id="diagnostic-exact-case",
                                route_kind="opposite", authorization=True, expected_frames=3)
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "native.json"
            self.assertEqual(len(save(path, packet)), 64)
            packet["rows"][0]["walker_id"] = 99
            with self.assertRaisesRegex(ValueError, "unsealed"):
                save(path, packet)

    def test_saved_join_rejects_tamper_and_source_drift(self):
        s = site()
        packet = acquire(Adapter(), site=s, site_sha256=digest(s), case_id="diagnostic-exact-case",
                         route_kind="opposite", authorization=True,
                         blueprint_id="walker.pedestrian.0001", frames=3)
        packet["rows"][1]["camera_frames"]["overview"] = 99
        with self.assertRaisesRegex(ValueError, "unsealed"):
            measure_acquisition(s, packet, case_id="diagnostic-exact-case", route_kind="opposite",
                                authorization=True, expected_frames=3, allow_diagnostic=True)
        packet["rows_sha256"] = __import__("native_acquisition")._sha(packet["rows"])
        with self.assertRaisesRegex(ValueError, "camera"):
            measure_acquisition(s, packet, case_id="diagnostic-exact-case", route_kind="opposite",
                                authorization=True, expected_frames=3, allow_diagnostic=True)
        packet["rows"][1]["camera_frames"]["overview"] = 1
        packet["rows_sha256"] = __import__("native_acquisition")._sha(packet["rows"])
        s["devices"][0]["official_source"] = "changed"
        with self.assertRaisesRegex(ValueError, "site or route"):
            measure_acquisition(s, packet, case_id="diagnostic-exact-case", route_kind="opposite",
                                authorization=True, expected_frames=3, allow_diagnostic=True)

    def test_rejects_site_drift_before_spawn(self):
        s = site()
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            acquire(Adapter(), site=s, site_sha256="b" * 64, case_id="diagnostic-exact-case",
                    route_kind="adjacent", authorization=False, blueprint_id="walker.pedestrian.0001", frames=3)

    def test_rejects_frame_identity_provenance_and_camera_gaps_with_cleanup(self):
        s = site()
        for problem, expected in (("frame", "discontinuity"), ("identity", "identity"),
                                  ("provenance", "provenance"), ("camera", "camera")):
            with self.subTest(problem=problem):
                adapter = Adapter(problem)
                with self.assertRaisesRegex(ValueError, expected):
                    acquire(adapter, site=s, site_sha256=digest(s), case_id="diagnostic-exact-case",
                            route_kind="opposite", authorization=True,
                            blueprint_id="walker.pedestrian.0001", frames=3)
                self.assertTrue(adapter.cleaned)

    def test_production_requires_full_body_and_velocity(self):
        class Production(Adapter):
            is_diagnostic = False
            def actor_state(self, actor):
                return {"actor_id": 7, "blueprint": "walker.pedestrian.0001",
                        "body_vertices_m": [[0,0,0], [1,0,0], [0,1,0], [1,1,0]],
                        "velocity_mps": [1,0,0], "heading_deg": 0}
        s = site()
        packet = acquire(Production(), site=s, site_sha256=digest(s),
                         case_id="diagnostic-exact-case", route_kind="opposite",
                         authorization=True, blueprint_id="walker.pedestrian.0001",
                         frames=3)
        self.assertFalse(packet["diagnostic"])
        self.assertEqual(packet["rows"][1]["actor_state"]["actor_id"], 7)
        measured = measure_acquisition(s, packet, case_id="diagnostic-exact-case",
                                       route_kind="opposite", authorization=True, expected_frames=3)
        self.assertTrue(measured["camera_frames_verified"])
        packet["rows"][1]["actor_state"]["body_vertices_m"] = []
        packet["rows_sha256"] = __import__("native_acquisition")._sha(packet["rows"])
        with self.assertRaisesRegex(ValueError, "body and velocity"):
            measure_acquisition(s, packet, case_id="diagnostic-exact-case",
                                route_kind="opposite", authorization=True, expected_frames=3)
        class Bad(Production):
            def actor_state(self, actor):
                value = super().actor_state(actor)
                value["body_vertices_m"] = []
                return value
        with self.assertRaisesRegex(ValueError, "body and velocity"):
            acquire(Bad(), site=s, site_sha256=digest(s),
                    case_id="diagnostic-exact-case", route_kind="opposite",
                    authorization=True, blueprint_id="walker.pedestrian.0001",
                    frames=3)


if __name__ == "__main__": unittest.main()
