import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_acquisition import acquire, body_footprint
from finalize_observables import finalize
from intersection_observables import SourceError


CASE = "testing__C110969__NRS-484B-450-1c__motor_vehicle_driver__inside_stop"
BOUNDARY = {"map_id": "reviewed-map", "highway_status": "reviewed_highway",
            "joining_roadways": True, "boundary_method": "reviewed roadway lateral line extension",
            "intersection_polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "source_refs": [{"path": "reviewed-map-packet", "sha256": "source-hash"}]}


class Actor:
    bounding_box = S(location=S(x=0, y=0), extent=S(x=1, y=0.5))

    def get_transform(self):
        return S(location=S(x=5, y=5), rotation=S(yaw=90))

    def get_velocity(self):
        return S(x=0, y=0, z=0)


class World:
    def __init__(self, *, map_name="reviewed-map", gap=False, delta=0.05):
        self.name, self.gap, self.delta, self.frame = map_name, gap, delta, 0

    def get_map(self):
        return S(name=self.name)

    def get_settings(self):
        return S(synchronous_mode=True, fixed_delta_seconds=self.delta)

    def tick(self):
        self.frame += 2 if self.gap and self.frame else 1

    def get_snapshot(self):
        return S(frame=self.frame, timestamp=S(elapsed_seconds=self.frame * 0.05))


class Controller:
    stopped = False

    def step(self, index, actor):
        return {"source": "original_controller_request", "brake": 1.0, "tick_index": index}

    def stop(self, actor):
        self.stopped = True


class Observer:
    def observe(self, snapshot, actor):
        return {"source_ref": f"native:{snapshot.frame}:activity", "activity_observation": "intentional stop request observed",
                "traffic_conflict_observation": None, "law_direction_observation": None,
                "officer_direction_observation": None, "device_direction_observation": None}


class AcquisitionTests(unittest.TestCase):
    def test_native_footprint_rotates_actual_box(self):
        points = body_footprint(Actor())
        self.assertEqual(points, [[5.5, 4], [5.5, 6], [4.5, 6], [4.5, 4]])

    def test_acquisition_finalizer_and_source_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE, "run-1", root, 3)
            self.assertFalse(receipt["physical_acceptance_claimed"])
            measured = finalize(root / "source-manifest.json")
            self.assertEqual([x["within_or_touching_boundary"] for x in measured["frames"]], [True] * 3)
            trace = json.loads((root / "trace.json").read_text())
            trace["samples"][1]["speed_mps"] = 8
            (root / "trace.json").write_text(json.dumps(trace))
            with self.assertRaisesRegex(SourceError, "source seal differs"):
                finalize(root / "source-manifest.json")

    def test_native_map_and_tick_gap_rejected_with_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SourceError, "map identity"):
                acquire(World(map_name="other"), Actor(), BOUNDARY, Controller(), Observer(), CASE, "run-1", Path(tmp), 3)
            control = Controller()
            with self.assertRaisesRegex(SourceError, "frame or 20 Hz time gap"):
                acquire(World(gap=True), Actor(), BOUNDARY, control, Observer(), CASE, "run-1", Path(tmp), 3)
            self.assertTrue(control.stopped)

    def test_observer_and_rate_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SourceError, "20 Hz"):
                acquire(World(delta=0.1), Actor(), BOUNDARY, Controller(), Observer(), CASE, "run-1", Path(tmp), 3)
            bad_observer = S(observe=lambda snapshot, actor: {"activity_observation": "requested"})
            with self.assertRaisesRegex(SourceError, "independent original activity"):
                acquire(World(), Actor(), BOUNDARY, Controller(), bad_observer, CASE, "run-1", Path(tmp), 3)

    def test_case_or_frame_join_tamper_rejected_even_after_resealing(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE, "run-1", root, 3)
            manifest = json.loads((root / "source-manifest.json").read_text())
            activity = json.loads((root / "activity.json").read_text())
            activity["activity_samples"][1]["frame"] = 99
            raw = (json.dumps(activity) + "\n").encode()
            (root / "activity.json").write_bytes(raw)
            manifest["activity"]["sha256"] = hashlib.sha256(raw).hexdigest()
            (root / "source-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(SourceError, "frame join differs"):
                finalize(root / "source-manifest.json")


if __name__ == "__main__":
    unittest.main()
