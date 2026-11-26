import json
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from path_observation import ASSIGNMENT, measure
from path_route import select_route
from source_site import REQUIRED, load_reviewed_site
from source_deferred_runner import capture_original, CAMERAS
from analysis import _original, analyze
from compare_saved import compare


class PathPackageTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-only",
                "ego_device_type": "electric_scooter", "ego_actor_id": "rider-a",
                "roadway_id": "road-a", "path_id": "path-a",
                "path_designation_source": "synthetic-sign-a",
                "path_adjacent_to_roadway": True, "sidewalk_status": "absent",
                "path_usability_status": "unresolved",
                "path_condition_source": "synthetic-condition-a",
                "access_restrictions_source": "synthetic-access-a",
                "frames": [{"time_s": i * 0.05, "ego_body_on_roadway": False,
                            "ego_body_on_designated_path": True} for i in range(3)]}

    def site(self):
        return {"assignment_id": ASSIGNMENT, "map_id": "synthetic-map",
                "roadway_id": "road-a", "path_id": "path-a",
                "path_designation_source": "synthetic-sign-a",
                "path_adjacent_to_roadway": True, "sidewalk_status": "absent",
                "path_usability_status": "unresolved",
                "path_polygon": [[0, 0], [8, 0], [8, 2], [0, 2]],
                "roadway_polygon": [[0, 3], [8, 3], [8, 7], [0, 7]],
                "route_candidates": {"path": [[1, 1], [7, 1]],
                                     "roadway": [[1, 5], [7, 5]],
                                     "escape": [[1, 1], [7, 5]]}}

    def run_packet(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def run_site(self, site, candidate, target):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "site.json"
            p.write_text(json.dumps(site), encoding="utf-8")
            return select_route(p, candidate, target)

    def test_path_ride_keeps_usability_unresolved(self):
        r = self.run_packet(self.packet())
        self.assertTrue(r["path_use_observed"])
        self.assertFalse(r["roadway_use_observed"])
        self.assertEqual(r["path_usability_status"], "unresolved")

    def test_roadway_ride_detected(self):
        p = self.packet()
        p["frames"][1]["ego_body_on_roadway"] = True
        self.assertTrue(self.run_packet(p)["roadway_use_observed"])

    def test_all_covered_devices(self):
        for device in ("bicycle", "electric_bicycle", "electric_scooter"):
            p = self.packet()
            p["ego_device_type"] = device
            self.assertEqual(self.run_packet(p)["ego_device_type"], device)

    def test_missing_access_source_rejected(self):
        p = self.packet()
        del p["access_restrictions_source"]
        with self.assertRaisesRegex(ValueError, "access"):
            self.run_packet(p)

    def test_path_and_roadway_routes_constructed(self):
        self.assertEqual(self.run_site(self.site(), "path", "path")["target_facility"], "path")
        self.assertEqual(self.run_site(self.site(), "roadway", "roadway")["target_facility"], "roadway")

    def test_route_leaving_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "leaves"):
            self.run_site(self.site(), "escape", "path")

    def test_sidewalk_cell_mismatch_rejected(self):
        s = self.site()
        s["sidewalk_status"] = "present"
        with self.assertRaisesRegex(ValueError, "sidewalk"):
            self.run_site(s, "path", "path")

    def reviewed_packet(self, directory):
        directory = Path(directory)
        case_id = ASSIGNMENT + "__electric_scooter__path__usable_path"
        site = self.site()
        site.update({"case_id": case_id, "ego_device_type": "electric_scooter",
                     "path_usability_status": "usable",
                     "municipal_jurisdiction_reviewed": True})
        site_path = directory / "site.json"
        site_path.write_text(json.dumps(site))
        adapter_path = directory / "adapter.py"
        adapter_path.write_text("# source-shaped adapter test only\n")
        sources = {}
        for name in REQUIRED:
            path = directory / (name + ".txt")
            path.write_text("source-shaped test only: " + name)
            sources[name] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = {"assignment_id": ASSIGNMENT, "case_id": case_id,
                    "source_kind": "reviewed_original", "synthetic": False,
                    "site_sha256": hashlib.sha256(site_path.read_bytes()).hexdigest(),
                    "native_adapter_sha256": hashlib.sha256(adapter_path.read_bytes()).hexdigest(),
                    "sources": sources}
        manifest_path = directory / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        return manifest_path, site_path, case_id

    def native_attempt(self, directory, case_id):
        directory = Path(directory)
        root = directory / "package"
        root.mkdir()
        config = {"assignment_id": ASSIGNMENT, "law_id": "LVMC-11-40-120",
                  "cell_id": "C233829", "actor": "cycle_or_scooter_operator",
                  "selected_case_id": case_id, "rate_hz": 20, "duration_s": 45,
                  "cameras": list(CAMERAS), "required_atoms": []}
        (root / "config.json").write_text(json.dumps(config))
        output = directory / "attempt"
        output.mkdir()
        for name in ("config.json", "construction.json", "runner.py"):
            (output / name).write_text((root / "config.json").read_text() if name == "config.json" else "original test source\n")
        return root, output

    def test_reviewed_source_gate_selects_path(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            manifest, site, case_id = self.reviewed_packet(d)
            result = load_reviewed_site(manifest, site, case_id, "electric_scooter", "path", "usable")
            self.assertEqual(result["route"]["target_facility"], "path")
            self.assertFalse(result["physical_path_usability_verified"])

    def test_reviewed_source_gate_rejects_changed_source(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            manifest, site, case_id = self.reviewed_packet(d)
            (Path(d) / "path_access.txt").write_text("changed")
            with self.assertRaisesRegex(ValueError, "changed original source"):
                load_reviewed_site(manifest, site, case_id, "electric_scooter", "path", "usable")

    def test_reviewed_source_gate_rejects_case_mismatch(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            manifest, site, case_id = self.reviewed_packet(d)
            with self.assertRaisesRegex(ValueError, "case identity"):
                load_reviewed_site(manifest, site, case_id + "-other", "electric_scooter", "path", "usable")

    def test_full_source_shaped_native_capture_and_cleanup(self):
        class Actor:
            destroyed = False
            def destroy(self): self.destroyed = True

        class Snapshot:
            def __init__(self, frame):
                self.frame = frame
                self.timestamp = type("Timestamp", (), {"elapsed_seconds": frame / 20})()

        class Adapter:
            def __init__(self):
                self.frame = 99
                self.actor = Actor()
                self.restored = False
                self.closed_cameras = False
            def provenance(self): return "original_native"
            def spawn_rider(self, device, origin):
                assert device == "electric_scooter" and origin == [1, 1]
                return self.actor
            def pipeline_client(self): return self
            def start_cameras(self, output, names): self.output = output
            def set_rider_target(self, actor, route, index, count):
                assert actor is self.actor and count == 900
            def tick_world(self): self.frame += 1
            def world(self): return self
            def get_snapshot(self): return Snapshot(self.frame)
            def sample_rider(self, actor):
                return {"native_frame": self.frame, "ego_actor_id": "rider-1",
                        "ego_device_type": "electric_scooter",
                        "body_corners_xy": [[2, 0.8], [2.2, 0.8], [2.2, 1], [2, 1]]}
            def camera_frame_ids(self, frame): return {name: frame for name in CAMERAS}
            def finish_cameras(self):
                for name in CAMERAS: (self.output / (name + ".mkv")).write_bytes(b"source-shaped-media")
                self.closed_cameras = True
                return {name: self.output / (name + ".mkv") for name in CAMERAS}
            def abort_cameras(self): self.closed_cameras = True
            def finish_native_capture(self, output, rows):
                (output / "trace.jsonl").write_text("original-shaped-trace\n")
                return ["trace.jsonl"]
            def restore_world(self): self.restored = True; return True

        class Pipeline:
            def __init__(self, client, actor, output, case_id, required_observations): self.closed = False
            def capture(self, frame, elapsed): return {"frame": frame, "time_s": elapsed}
            def close(self, confirmed): self.closed = True

        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            manifest, site, case_id = self.reviewed_packet(d)
            root, attempt = self.native_attempt(d, case_id)
            adapter = Adapter()
            receipt = capture_original(adapter, manifest, site, Path(d) / "adapter.py",
                                       attempt, root=root, pipeline_factory=Pipeline)
            self.assertEqual(receipt["frames"], 900)
            self.assertFalse(receipt["physical_path_usability_verified"])
            self.assertTrue(adapter.actor.destroyed and adapter.restored and adapter.closed_cameras)
            self.assertEqual(len((attempt / "rider-history.jsonl").read_text().splitlines()), 900)
            self.assertEqual(len((attempt / "camera-frame-map.jsonl").read_text().splitlines()), 900)
            seal = json.loads((attempt / "capture-seal.json").read_text())
            self.assertEqual(seal["provenance_kind"], "native")
            self.assertEqual(seal["sources"]["reviewed-site/path_access.txt"],
                             hashlib.sha256((Path(d) / "path_access.txt").read_bytes()).hexdigest())
            site_packet, rows, source_hashes = _original(attempt, case_id,
                                                          "electric_scooter", "path", "usable")
            self.assertEqual(len(rows), 900)
            self.assertEqual(site_packet["path_id"], "path-a")
            self.assertIn("capture-seal.json", source_hashes)
            (attempt / "rider-history.jsonl").write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "sealed original source changed"):
                _original(attempt, case_id, "electric_scooter", "path", "usable")

    def test_saved_diagnostic_finalizer_separates_position_and_usability(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            directory = Path(d)
            case_id = ASSIGNMENT + "__electric_scooter__roadway__usable_path"
            site = self.site()
            site.update({"case_id": case_id, "ego_device_type": "electric_scooter",
                         "path_usability_status": "usable",
                         "path_condition_source": "synthetic-condition-only",
                         "access_restrictions_source": "synthetic-access-only"})
            (directory / "site.json").write_text(json.dumps(site))
            (directory / "diagnostic-source-note.json").write_text(json.dumps({
                "source_kind": "synthetic_diagnostic_fixture",
                "accepted_original_source": False, "case_id": case_id}))
            rows = [{"frame_index": i, "native_frame": 100 + i,
                     "time_s": i / 20, "ego_actor_id": "rider-1",
                     "ego_device_type": "electric_scooter",
                     "ego_body_on_roadway": True,
                     "ego_body_on_designated_path": False} for i in range(900)]
            (directory / "rider-history.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            (directory / "trace.jsonl").write_text("".join(json.dumps({
                "frame": 100 + i, "time_s": i / 20, "position_m": [i * 0.01, 0, 0]}) + "\n"
                for i in range(900)))
            (directory / "video_frames.jsonl").write_text("".join(json.dumps({
                "video_frame": i, "carla_frame": 100 + i,
                "native_frame": 100 + i, "time_s": i / 20}) + "\n" for i in range(900)))
            description = {"channels": [{"name": name, "unit": "structured"} for name in
                          ("rider_facility", "path_context", "device_classification",
                           "camera_frame_identity")]}
            config = {"assignment_id": ASSIGNMENT, "law_id": "LVMC-11-40-120",
                      "cell_id": "C233829", "selected_case_id": case_id,
                      "case": {"recording_description": description}}
            (directory / "config.json").write_text(json.dumps(config))
            report = analyze(directory)
            self.assertTrue(report["measurements"]["rider_facility_use"]["value"]["roadway_use_observed"])
            self.assertEqual(report["measurements"]["rider_facility_use"]["value"]["path_usability_status"], "usable")
            self.assertFalse(report["physical_acceptance_claimed"])
            self.assertFalse(report["legal_verdict_claimed"])
            self.assertEqual(len((directory / "channel-rider_facility.jsonl").read_text().splitlines()), 900)

    def comparison_receipt(self, device, facility, condition):
        case_id = ASSIGNMENT + "__" + device + "__" + facility + "__" + condition + "_path"
        return {"format": "c233829-original-delivery-audit-v1",
                "case_id": case_id, "device_type": device,
                "target_facility": facility, "path_usability_context": condition,
                "map_id": "source-shaped-map", "roadway_id": "road-a", "path_id": "path-a",
                "route_waypoints": [[1, 1], [7, 1]] if facility == "path" else [[1, 5], [7, 5]],
                "original_frame_count": 900,
                "camera_decodes": {name: {"decoded_frames": 900, "width": 1920 if name == "overview" else 1280,
                                          "height": 1080 if name == "overview" else 720} for name in CAMERAS},
                "fixed_sources": {name: "same-source" for name in (*REQUIRED, "native_adapter")},
                "physical_completion": True, "legal_status": "unresolved"}

    def test_all_route_comparisons_and_source_isolation(self):
        for device in ("bicycle", "electric_bicycle", "electric_scooter"):
            left = self.comparison_receipt(device, "path", "usable")
            right = self.comparison_receipt(device, "roadway", "usable")
            result = compare(left, right, device + "_path_vs_roadway")
            self.assertEqual(result["case_ids"], [left["case_id"], right["case_id"]])
            right["fixed_sources"]["path_designation"] = "changed"
            with self.assertRaisesRegex(ValueError, "path_designation"):
                compare(left, right, device + "_path_vs_roadway")

    def test_path_condition_comparison_keeps_route_fixed(self):
        left = self.comparison_receipt("electric_scooter", "roadway", "usable")
        right = self.comparison_receipt("electric_scooter", "roadway", "unusable")
        right["fixed_sources"]["path_condition"] = "reviewed-different-condition"
        result = compare(left, right, "path_usability_context")
        self.assertEqual(result["comparison_id"], "path_usability_context")
        right["route_waypoints"] = [[2, 5], [7, 5]]
        with self.assertRaisesRegex(ValueError, "route changed"):
            compare(left, right, "path_usability_context")


if __name__ == "__main__":
    unittest.main()
