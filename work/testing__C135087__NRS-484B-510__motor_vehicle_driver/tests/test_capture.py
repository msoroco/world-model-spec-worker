"""CPU source-custody tests; fake pixels and motion are diagnostic only."""

import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
import sys
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


zone = load("restricted_zone")
site = load("reviewed_site")
capture = load("native_capture")
audit = load("zone_audit")
saved = load("saved_audit")
delivery = load("delivery_audit")
comparison = load("comparison_audit")
_pixel = io.BytesIO()
Image.new("RGB", (1, 1), (255, 0, 0)).save(_pixel, format="PNG")
PNG = _pixel.getvalue()


class World:
    def load_map(self, *args): pass
    def mark_zone(self, *args): pass
    def spawn_vehicle(self, role, *args): return role
    def spawn_pedestrian(self, role, *args): return role
    def set_route(self, *args): pass
    def schedule(self, *args): pass


class Adapter:
    world = World()

    def __init__(self, case, missing=None, wrong_map=False):
        self.case = case
        self.missing = missing
        self.wrong_map = wrong_map
        self.index = -1

    def attach_cameras(self, actors, views): return dict.fromkeys(views, object())
    def provenance(self): return "diagnostic_fixture"
    def request_control(self, actors, plan, index): self.index = index

    def tick_and_read(self, actors, cameras):
        i = self.index
        state = dict(case_id=self.case, map_id="wrong" if self.wrong_map else "reviewed-map",
                     subject_station_m=16, subject_speed_mps=0,
                     entrant_station_m=4 if i < 250 else 11,
                     entrant_speed_mps=2 if i < 250 else 0,
                     entrant_waiting=250 <= i < 400,
                     passenger_exchange_active=160 <= i < 300,
                     passenger_station_m=16,
                     passenger_boarding_state="approaching" if i < 160 else "boarding" if i < 300 else "aboard",
                     entrant_access_blocked=250 <= i < 400,
                     entrant_parking_task_active=True)
        if self.missing == "state": state.pop("entrant_parking_task_active")
        pixels = {view: PNG for view in cameras}
        if self.missing == "camera": pixels.pop("passenger_door")
        frame, time_s = 1000 + i, 100 + i / 20
        return dict(frame=frame, time_s=time_s, state=state, camera_png=pixels,
                    trace={"frame": frame, "time_s": time_s},
                    video_frame={"video_frame": i, "carla_frame": frame, "time_s": time_s})

    def finalize_media(self, output, views, mappings):
        paths = {}
        for name in (*views, "raw"):
            path = output / (name + ".mkv")
            path.write_bytes(b"diagnostic encoded-media placeholder")
            paths[name] = path
        return paths

    def close(self): return True


class OriginalShapeAdapter(Adapter):
    """Structural audit test double; never a real Native source."""

    def provenance(self): return "original_native"


class CaptureTests(unittest.TestCase):
    def plan(self):
        return zone.ZonePlan(case_id="test-case", map_id="reviewed-map", zone_start_m=10,
                             zone_end_m=30, subject_stop_m=16, entrant_start_m=0,
                             entrant_destination_m=23, entrant_departure_s=6,
                             subject_departure_s=24, passenger_exchange_start_s=8,
                             passenger_exchange_end_s=15)

    def packet(self, root, plan):
        root.mkdir(parents=True, exist_ok=True)
        sources = {}
        for role in site.ROLES:
            path = root / (role + ".txt")
            path.write_text("reviewed " + role + "\n")
            sources[role] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        path = root / "site.json"
        path.write_text(json.dumps(dict(case_id=plan.case_id, cell_id="C135087",
                                        map_id=plan.map_id, zone_start_m=plan.zone_start_m,
                                        zone_end_m=plan.zone_end_m,
                                        restricted_purpose=plan.restricted_purpose,
                                        reviewer="independent reviewer", reviewed_at="source date",
                                        sources=sources)))
        return path

    def test_original_capture_and_existing_source_audit(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            plan = self.plan()
            packet = self.packet(root, plan)
            output = root / "attempt"
            result = capture.capture(Adapter(plan.case_id), plan, packet, output,
                                     allow_diagnostic=True)
            self.assertEqual(result["frame_count"], 900)
            measured = audit.audit_original_frames(output / "original-attempt/history.jsonl",
                                                   output / "original-attempt/context.json",
                                                   output / "original-attempt/seal.json", plan.case_id)
            self.assertEqual(measured["entrant_waiting_frames"], 150)
            self.assertFalse(result["physical_acceptance_claimed"])
            packet_sha = hashlib.sha256((output / "original-attempt/site-packet.json").read_bytes()).hexdigest()
            reviewed = saved.audit(output, plan.case_id, packet_sha, allow_diagnostic=True)
            self.assertEqual(reviewed["decoded_original_pixels"]["overview"], 900)
            self.assertEqual(reviewed["legal_status"], "unresolved_judgment")
            with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                saved.audit(output, plan.case_id, packet_sha)
            with self.assertRaisesRegex(ValueError, "reviewed site hash"):
                saved.audit(output, plan.case_id, "0" * 64, allow_diagnostic=True)
            with self.assertRaisesRegex(ValueError, "overwrite"):
                capture.capture(Adapter(plan.case_id), plan, packet, output,
                                allow_diagnostic=True)

    def test_saved_pixel_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            plan = self.plan()
            packet = self.packet(root, plan)
            output = root / "attempt"
            capture.capture(Adapter(plan.case_id), plan, packet, output,
                            allow_diagnostic=True)
            site_sha = hashlib.sha256((output / "original-attempt/site-packet.json").read_bytes()).hexdigest()
            archive = output / "original-attempt/overview.zip"
            with archive.open("ab") as stream:
                stream.write(b"tamper")
            with self.assertRaisesRegex(ValueError, "archive missing or stale"):
                saved.audit(output, plan.case_id, site_sha, allow_diagnostic=True)

    def test_saved_video_map_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            plan = self.plan()
            packet = self.packet(root, plan)
            output = root / "attempt"
            capture.capture(Adapter(plan.case_id), plan, packet, output,
                            allow_diagnostic=True)
            site_sha = hashlib.sha256((output / "original-attempt/site-packet.json").read_bytes()).hexdigest()
            mapping = output / "video_frames.jsonl"
            mapping.write_text(mapping.read_text().replace('"video_frame": 0', '"video_frame": 1', 1))
            with self.assertRaisesRegex(ValueError, "trace/video map missing or stale"):
                saved.audit(output, plan.case_id, site_sha, allow_diagnostic=True)

    def test_delivery_rejects_diagnostic_and_external_review_tamper(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            plan = self.plan()
            packet = self.packet(root, plan)
            output = root / "attempt"
            capture.capture(Adapter(plan.case_id), plan, packet, output,
                            allow_diagnostic=True)
            site_sha = hashlib.sha256((output / "original-attempt/site-packet.json").read_bytes()).hexdigest()
            review = root / "review.json"
            review.write_text(json.dumps({"case_id": plan.case_id}))
            review_sha = hashlib.sha256(review.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                delivery.audit(output, plan.case_id, site_sha, review, review_sha)
            with self.assertRaisesRegex(ValueError, "packet missing or stale"):
                delivery.audit(output, plan.case_id, site_sha, review, "0" * 64)

    def test_delivery_review_requires_complete_pixel_citations(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            plan = self.plan()
            packet = self.packet(root, plan)
            output = root / "attempt"
            capture.capture(OriginalShapeAdapter(plan.case_id), plan, packet, output)
            site_sha = hashlib.sha256((output / "original-attempt/site-packet.json").read_bytes()).hexdigest()
            row = json.loads((output / "original-attempt/history.jsonl").read_text().splitlines()[0])
            citation = row["camera_sources"]["overview"]["sha256"]
            review = root / "review.json"
            observations = {topic: dict(observed=True, note="structural test citation",
                                        frame=0, view="overview", pixel_sha256=citation)
                            for topic in delivery.OBSERVATIONS}
            packet_data = dict(case_id=plan.case_id, site_packet_sha256=site_sha,
                               reviewer="test double", reviewed_at="test date",
                               observations=observations)
            original_dimensions = saved.DIMENSIONS.copy()
            try:
                saved.DIMENSIONS.update({view: (1, 1) for view in saved.VIEWS})
                review.write_text(json.dumps(packet_data))
                review_sha = hashlib.sha256(review.read_bytes()).hexdigest()
                result = delivery.audit(output, plan.case_id, site_sha, review, review_sha)
                self.assertTrue(result["physical_completion"])
                packet_data["observations"]["entrant_approach"]["pixel_sha256"] = "0" * 64
                review.write_text(json.dumps(packet_data))
                bad_sha = hashlib.sha256(review.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, "pixel citation stale"):
                    delivery.audit(output, plan.case_id, site_sha, review, bad_sha)
                packet_data["observations"].pop("entrant_approach")
                review.write_text(json.dumps(packet_data))
                incomplete_sha = hashlib.sha256(review.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, "review incomplete"):
                    delivery.audit(output, plan.case_id, site_sha, review, incomplete_sha)
            finally:
                saved.DIMENSIONS.clear()
                saved.DIMENSIONS.update(original_dimensions)

    def test_comparison_checks_independent_original_sources(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            left_plan = self.plan()
            right_plan = zone.ZonePlan(**{**left_plan.__dict__, "case_id": "other-case"})
            left_packet = self.packet(root / "left-sources", left_plan)
            right_packet = self.packet(root / "right-sources", right_plan)
            left, right = root / "left", root / "right"
            capture.capture(OriginalShapeAdapter(left_plan.case_id), left_plan, left_packet, left)
            capture.capture(OriginalShapeAdapter(right_plan.case_id), right_plan, right_packet, right)
            left_sha = hashlib.sha256((left / "original-attempt/site-packet.json").read_bytes()).hexdigest()
            right_sha = hashlib.sha256((right / "original-attempt/site-packet.json").read_bytes()).hexdigest()
            old_dimensions = saved.DIMENSIONS.copy()
            try:
                saved.DIMENSIONS.update({view: (1, 1) for view in saved.VIEWS})
                result = comparison.audit(left, right, left_plan.case_id, right_plan.case_id,
                                          left_sha, right_sha)
                self.assertTrue(result["fixed_context_source_matched"])
                with self.assertRaisesRegex(ValueError, "independent reviewed site hashes"):
                    comparison.audit(left, right, left_plan.case_id, right_plan.case_id,
                                     left_sha, "")
                with self.assertRaisesRegex(ValueError, "reviewed site hash mismatch"):
                    comparison.audit(left, right, left_plan.case_id, right_plan.case_id,
                                     left_sha, "0" * 64)
            finally:
                saved.DIMENSIONS.clear()
                saved.DIMENSIONS.update(old_dimensions)

    def test_missing_or_stale_reviewed_source_fails_before_capture(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            plan = self.plan()
            packet = self.packet(root, plan)
            (root / "zone_authority.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "stale"):
                capture.capture(Adapter(plan.case_id), plan, packet, root / "attempt",
                                allow_diagnostic=True)
            self.assertFalse((root / "attempt").exists())

    def test_original_readback_and_camera_failures_do_not_seal(self):
        for label, adapter, expected in (("state", Adapter("test-case", missing="state"), "state/readback"),
                                         ("camera", Adapter("test-case", missing="camera"), "pixel sources"),
                                         ("map", Adapter("test-case", wrong_map=True), "case/map")):
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
                root = Path(tmp)
                plan = self.plan()
                packet = self.packet(root, plan)
                with self.assertRaisesRegex(ValueError, expected):
                    capture.capture(adapter, plan, packet, root / "attempt",
                                    allow_diagnostic=True)
                self.assertFalse((root / "attempt/original-attempt/seal.json").exists())

    def test_diagnostic_adapter_rejected_in_original_mode(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            plan = self.plan()
            packet = self.packet(root, plan)
            with self.assertRaisesRegex(ValueError, "original Native provenance"):
                capture.capture(Adapter(plan.case_id), plan, packet, root / "attempt")
            self.assertFalse((root / "attempt").exists())


if __name__ == "__main__":
    unittest.main()
