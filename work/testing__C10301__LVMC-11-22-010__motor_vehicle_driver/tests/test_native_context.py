import importlib.util
from pathlib import Path
import types
import unittest


module_path = Path(__file__).resolve().parents[1] / "native_context.py"
spec = importlib.util.spec_from_file_location("native_context", module_path)
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)

CASE = "testing__C10301__LVMC-11-22-010__motor_vehicle_driver__steady_travel"
OBSERVED = {
    "native_frame": 100, "native_time_s": 5.0,
    "map_sha256": "a" * 64, "marking_source_sha256": "b" * 64,
    "parking_source_sha256": "c" * 64,
    "jurisdiction_source_sha256": "d" * 64,
    "marking_native_verified": True, "parking_native_verified": True,
    "body_footprint_xy_m": [[-1.0, 0.0], [1.0, 0.0], [1.0, 2.0], [-1.0, 2.0]],
    "marking_polygons_xy_m": [[[0.5, 1.5], [1.5, 1.5], [1.5, 2.5], [0.5, 2.5]]],
    "time_to_conflict_s": None, "traffic_signal": "none",
    "signal_native_verified": True,
}


class NativeContextTests(unittest.TestCase):
    def test_native_adapter_reads_body_and_same_frame_site(self):
        actor = types.SimpleNamespace(
            get_transform=lambda: types.SimpleNamespace(
                location=types.SimpleNamespace(x=0.0, y=0.0),
                rotation=types.SimpleNamespace(yaw=0.0)),
            bounding_box=types.SimpleNamespace(extent=types.SimpleNamespace(x=1.0, y=0.5)))
        world = types.SimpleNamespace(get_map=lambda: types.SimpleNamespace(name="reviewed-map"))
        snap = types.SimpleNamespace(frame=100,
            timestamp=types.SimpleNamespace(elapsed_seconds=5.0))
        site = {"map_name": "reviewed-map", "map_sha256": "a" * 64,
                "jurisdiction_source_sha256": "d" * 64}
        mark = lambda w, f: {"native_frame": f, "native_verified": True,
            "source_sha256": "b" * 64,
            "polygons_xy_m": [[[0.5, 0.2], [1.5, 0.2], [1.5, 1.2], [0.5, 1.2]]]}
        park = lambda w, f: {"native_frame": f, "native_verified": True,
            "source_sha256": "c" * 64}
        signal = lambda a, w, f: {"native_frame": f, "native_verified": True, "state": "none"}
        conflict = lambda a, w, f: {"native_frame": f, "native_verified": True,
            "time_to_conflict_s": None}
        row = context.sample_from_native(actor, world, snap, CASE, site,
                                         mark, park, signal, conflict)
        self.assertTrue(row["straddles_marking"])
        self.assertEqual(row["native_frame"], 100)
        with self.assertRaisesRegex(ValueError, "marking original Native readback"):
            context.sample_from_native(actor, world, snap, CASE, site,
                lambda w, f: dict(mark(w, f), native_frame=f + 1), park, signal, conflict)

    def test_original_overlap_and_sealed_readback(self):
        row = context.sample_context(CASE, 100, 5.0, OBSERVED)
        self.assertTrue(row["straddles_marking"])
        self.assertEqual(len(row["source_sha256"]), 64)
        other = dict(OBSERVED, body_footprint_xy_m=[[4.0, 0.0], [6.0, 0.0], [6.0, 2.0], [4.0, 2.0]])
        row2 = context.sample_context(CASE, 100, 5.0, other)
        self.assertFalse(row2["straddles_marking"])
        self.assertNotEqual(row["source_sha256"], row2["source_sha256"])

    def test_rejects_unverified_or_draft_geometry(self):
        for change, message in [
            ({"marking_native_verified": False}, "marking readback"),
            ({"parking_native_verified": False}, "parking designation"),
            ({"signal_native_verified": False}, "signal readback"),
            ({"marking_source_sha256": "draft"}, "source hash"),
            ({"marking_polygons_xy_m": []}, "marking polygons"),
            ({"native_frame": 99}, "Native frame"),
            ({"native_time_s": 4.9}, "Native time"),
        ]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                context.sample_context(CASE, 100, 5.0, dict(OBSERVED, **change))

    def test_rejects_bad_geometry_and_missing_device(self):
        with self.assertRaisesRegex(ValueError, "nonfinite vertex"):
            context.sample_context(CASE, 100, 5.0,
                dict(OBSERVED, body_footprint_xy_m=[[float("nan"), 0], [1, 0], [0, 1]]))
        with self.assertRaisesRegex(ValueError, "signal readback"):
            context.sample_context(CASE, 100, 5.0,
                dict(OBSERVED, traffic_signal="blue"))
        with self.assertRaisesRegex(ValueError, "time to conflict"):
            context.sample_context(CASE, 100, 5.0,
                dict(OBSERVED, time_to_conflict_s=-1.0))
        with self.assertRaisesRegex(ValueError, "convex"):
            context.sample_context(CASE, 100, 5.0,
                dict(OBSERVED, marking_polygons_xy_m=[[
                    [0, 0], [2, 0], [0.5, 0.5], [2, 2], [0, 2]]]))


if __name__ == "__main__":
    unittest.main()
