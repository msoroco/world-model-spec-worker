"""Focused source and geometry checks without importing CARLA."""

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "bridge_observations.py"
sys.path.insert(0, str(SOURCE.parent))
SPEC = importlib.util.spec_from_file_location("bridge_observations", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def dossier(direction="a_to_b"):
    source = {"path": "review-record.txt", "sha256": hashlib.sha256(b"review record\n").hexdigest()}
    return {
        "format": "worker-bridge-site-v1", "case_id": "exact_case",
        "structure_kind": "bridge", "end_a_station_m": 0,
        "end_b_station_m": 60, "structure_id": "bridge-1", "ego_actor_id": 17,
        "travel_direction": direction, "declared_maximum_mph": 25,
        "maximum_declaration_source": source,
        "map_opendrive_sha256": "f" * 64,
        "stationing_source": source,
        "signs": {
            "end_a": {"station_m": -30.48, "face_direction": "toward_b",
                      "erected_source": source, "maintained_source": source},
            "end_b": {"station_m": 90.48, "face_direction": "toward_a",
                      "erected_source": source, "maintained_source": source},
        },
        "authority": {key: source for key in (
            "chapter_408_source", "highway_source", "investigation_source",
            "finding_source", "department_decision_source", "sign_causation_source")},
    }


def rows(direction="a_to_b"):
    start, step = (-55.0, 140.0 / 899) if direction == "a_to_b" else (115.0, -140.0 / 899)
    return [{"index": index, "original_frame": 1000 + index,
             "time_s": index / 20, "ego_station_m": start + index * step,
             "ego_speed_mps": 11.0, "ego_actor_id": 17}
            for index in range(900)]


class BridgeObservationsTest(unittest.TestCase):
    def test_all_administrative_sources_are_hash_bound(self):
        scratch = SOURCE.parents[2] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            path = Path(temp)
            (path / "review-record.txt").write_bytes(b"review record\n")
            site = path / "bridge-site.json"
            site.write_text(json.dumps(dossier(), sort_keys=True) + "\n")
            digest = hashlib.sha256(site.read_bytes()).hexdigest()
            self.assertEqual(MODULE.verify_site_bundle(site, digest, "exact_case")["case_id"], "exact_case")
            (path / "review-record.txt").write_bytes(b"changed\n")
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                MODULE.verify_site_bundle(site, digest, "exact_case")

    def test_both_approach_directions_cross_both_ends(self):
        for direction in ("a_to_b", "b_to_a"):
            with self.subTest(direction=direction):
                observation = MODULE.measure_crossing(dossier(direction), rows(direction), "exact_case")
                self.assertEqual(observation["original_frame_count"], 900)
                self.assertAlmostEqual(observation["sign_offsets_ft"]["end_a"], 100)
                self.assertAlmostEqual(observation["sign_offsets_ft"]["end_b"], 100)
                self.assertEqual(observation["structure_safety_judgment"], "unresolved")

    def test_sign_on_wrong_approach_rejected(self):
        site = dossier()
        site["signs"]["end_b"]["station_m"] = 50
        with self.assertRaisesRegex(ValueError, "wrong approach"):
            MODULE.validate_site(site, expected_case="exact_case")

    def test_missing_department_source_rejected(self):
        site = dossier()
        del site["authority"]["finding_source"]
        with self.assertRaisesRegex(ValueError, "chronology sources"):
            MODULE.validate_site(site, expected_case="exact_case")

    def test_missing_frame_rejected(self):
        trace = rows()
        trace.pop(450)
        with self.assertRaisesRegex(ValueError, "900 original"):
            MODULE.measure_crossing(dossier(), trace, "exact_case")

    def test_incomplete_crossing_rejected(self):
        trace = rows()
        for row in trace:
            row["ego_station_m"] = -55 + row["index"] * 0.1
        with self.assertRaisesRegex(ValueError, "exit incomplete"):
            MODULE.measure_crossing(dossier(), trace, "exact_case")

    def test_actor_switch_rejected(self):
        trace = rows()
        trace[200]["ego_actor_id"] = 18
        with self.assertRaisesRegex(ValueError, "actor identity"):
            MODULE.measure_crossing(dossier(), trace, "exact_case")


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def loaded_map_sha256(self): return "f" * 64
    def snapshot_settings(self): return {"fixed_delta_seconds": None}
    def configure_sync(self, **kwargs): self.calls.append(("configure_sync", kwargs))
    def readback_sync(self, **kwargs): return True
    def restore_settings(self, settings): self.calls.append(("restore", settings))
    def readback_restored(self, settings): return True
    def read_structure_ends(self, structure_id): return (0.0, 60.0)
    def spawn_vehicle(self, actor_class, direction, structure_id, *, spawn_adjust_m):
        self.calls.append(("spawn_vehicle", actor_class, direction, structure_id, spawn_adjust_m))
        return "ego"
    def read_vehicle_class(self, ego): return "motor_vehicle"
    def set_crossing_route(self, *args): self.calls.append(("route", *args))
    def set_target_speed_mps(self, *args): self.calls.append(("speed", *args))
    def spawn_sign(self, end, station, maximum, face):
        self.calls.append(("spawn_sign", end, station, maximum, face))
        return (end, station, face)
    def read_sign_station_and_face(self, sign): return sign[1:]
    def spawn_cameras(self, ego, names, site): return {name: name for name in names}
    def tick_capture(self, *args): raise AssertionError("not needed in construction test")
    def destroy(self, actor): self.calls.append(("destroy", actor))
    def actor_id(self, actor): return 17 if actor == "ego" else str(actor)


class BridgeConstructionTest(unittest.TestCase):
    def test_constructs_both_approaches_and_both_signs(self):
        import bridge_native
        for direction in ("a_to_b", "b_to_a"):
            with self.subTest(direction=direction):
                adapter = FakeAdapter()
                target = {"case_id": "exact_case", "travel_direction_request": direction,
                          "structure_kind_request": "bridge",
                          "requested_speed_delta_from_declared_maximum_mph": 5}
                built = bridge_native.construct(adapter, dossier(direction), target)
                self.assertEqual(built["requested_speed_mph"], 30)
                self.assertEqual(adapter.calls[0][-1], 0.0)
                self.assertEqual(len([c for c in adapter.calls if c[0] == "spawn_sign"]), 2)
                self.assertEqual(len(built["owned"]), 7)
                destroyed = bridge_native.destroy_owned(adapter, built["owned"], {})
                self.assertEqual(len(destroyed), 7)

    def test_rejects_wrong_map_and_face(self):
        import bridge_native
        target = {"case_id": "exact_case", "travel_direction_request": "a_to_b",
                  "structure_kind_request": "bridge",
                  "requested_speed_delta_from_declared_maximum_mph": 0}
        adapter = FakeAdapter()
        site = dossier()
        site["map_opendrive_sha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "OpenDRIVE differs"):
            bridge_native.construct(adapter, site, target)
        adapter = FakeAdapter()
        adapter.read_sign_station_and_face = lambda sign: (sign[1], "wrong")
        with self.assertRaisesRegex(ValueError, "sign station/face"):
            bridge_native.construct(adapter, dossier(), target)


class SavedAnalysisTest(unittest.TestCase):
    def test_source_bound_positive_and_missing_source_rejection(self):
        import analysis
        scratch = SOURCE.parents[2] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            attempt = Path(temp)
            site = attempt / "bridge-site.json"
            trace = attempt / "original-motion.jsonl"
            (attempt / "review-record.txt").write_bytes(b"review record\n")
            site.write_text(json.dumps(dossier(), sort_keys=True) + "\n")
            trace.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows()))
            receipt = {"case_id": "exact_case",
                       "site_sha256": hashlib.sha256(site.read_bytes()).hexdigest(),
                       "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}
            (attempt / "original-source-receipt.json").write_text(json.dumps(receipt) + "\n")
            result = analysis.build_report(attempt, "exact_case")
            self.assertTrue(result["analysis_complete"])
            self.assertFalse(result["legal_verdict_claimed"])
            self.assertEqual(len(result["measurements"]), 5)
            trace.unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: original-motion.jsonl"):
                analysis.build_report(attempt, "exact_case")


class NativeAcquisitionTest(unittest.TestCase):
    def test_original_tick_graph_join_and_owner_closure(self):
        import native_acquisition
        from PIL import Image
        import io
        scratch = SOURCE.parents[2] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            source = Path(temp) / "source"
            output = Path(temp) / "attempt"
            source.mkdir()
            output.mkdir()
            (output / "construction.json").write_text("{}\n")
            (source / "review-record.txt").write_bytes(b"review record\n")
            site_path = source / "bridge-site.json"
            site_path.write_text(json.dumps(dossier(), sort_keys=True) + "\n")
            image = Image.new("RGB", (2, 2), (40, 60, 80))
            png = io.BytesIO()
            image.save(png, format="PNG")
            class AcquisitionAdapter(FakeAdapter):
                client = object()
                def tick_capture(self, index, ego, cameras):
                    return rows_cache[index], {name: png.getvalue() for name in cameras}
            rows_cache = rows()
            capture_events = []
            class Capture:
                def __init__(self, client, ego, folder, case_id):
                    self.folder = folder
                    capture_events.append(("open", case_id))
                def capture(self, frame, time_s, extra=None):
                    capture_events.append(("capture", frame, time_s, extra["bridge_station_m"]))
                    return {"frame": frame}
                def close(self, confirmed=True):
                    capture_events.append(("close", confirmed))
            def fake_ffmpeg(command, cwd, check, timeout):
                (Path(cwd) / command[-1]).write_bytes(b"diagnostic video test only")
            case = {"case_id": "exact_case", "travel_direction_request": "a_to_b",
                    "structure_kind_request": "bridge",
                    "requested_speed_delta_from_declared_maximum_mph": 0}
            adapter = AcquisitionAdapter()
            with patch.object(native_acquisition.subprocess, "run", side_effect=fake_ffmpeg):
                result = native_acquisition.acquire(adapter, site_path,
                    hashlib.sha256(site_path.read_bytes()).hexdigest(), case, output,
                    capture_factory=Capture)
            self.assertEqual(result["original_frame_count"], 900)
            self.assertEqual(len([event for event in capture_events if event[0] == "capture"]), 900)
            self.assertEqual(capture_events[-1], ("close", True))
            self.assertEqual(len([call for call in adapter.calls if call[0] == "destroy"]), 7)
            self.assertTrue((output / "original-source-receipt.json").is_file())


if __name__ == "__main__":
    unittest.main()
