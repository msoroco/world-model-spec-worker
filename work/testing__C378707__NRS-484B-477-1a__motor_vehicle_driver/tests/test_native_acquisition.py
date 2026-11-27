"""CPU fixture for original Native acquisition, not a physical recording."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("native_acquisition", ROOT / "native_acquisition.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from alley_construction import ASSIGNMENT
from audit_original_attempt import audit
from analysis import measure_business_alley
from audit_comparisons import PAIRS, compare
from runner import _verify_site_sources

PNG = b"\x89PNG\r\n\x1a\n" + b"cpu-fixture-only"
MAP = b"cpu-fixture-opendrive"


class FakeOperator:
    native_attested = False

    def __init__(self, case_id, missing_camera=False, business_sha="a" * 64):
        self.case_id = case_id
        self.missing_camera = missing_camera
        self.business_sha = business_sha
        self.index = -1
        self.started = False
        self.cleaned = False

    def get_map_packet(self, case_id):
        self._same(case_id)
        sources = {name: {"path": "reviewed/" + name, "sha256": "a" * 64}
                   for name in ("alley", "business_frontage", "jurisdiction",
                                "vehicle_blueprint", "passenger_actor", "goods_actor")}
        sources["map"] = {"path": "reviewed/road.xodr", "sha256": hashlib.sha256(MAP).hexdigest()}
        sources["business_frontage"]["sha256"] = self.business_sha
        ordinance = case_id.endswith("__ordinance_passenger_authorized")
        if ordinance:
            sources["ordinance"] = {"path": "reviewed/ordinance", "sha256": "b" * 64}
        return {"case_id": case_id, "source_kind": "reviewed_original_native_site",
                "alley_kind": "business_district_alley", "public_highway_status": True,
                "business_district_reviewed": True, "jurisdiction_reviewed": True,
                "reviewed_sources": sources,
                "ordinance_status": "reviewed_authorizes_passenger_loading" if ordinance else "reviewed_no_applicable_override",
                "centerline_start_m": [0, 0], "centerline_end_m": [100, 0],
                "loading_station_m": 45, "loading_bay_reviewed": True,
                "passenger_zone_xy_m": [46, 3], "goods_zone_xy_m": [44, -3]}

    def _same(self, case_id):
        if case_id != self.case_id:
            raise ValueError("wrong fake case")

    def get_opendrive_bytes(self):
        return MAP

    def start(self, plan):
        self._same(plan["case_id"])
        self.started = True

    def read_actor_inventory(self):
        return {"ego_vehicle_id": 1, "ego_actual_blueprint": "fixture.vehicle",
                "ego_actual_dimensions_m": [4.5, 1.8],
                "passenger_actor_id": 2, "goods_actor_id": 3, "driver_actor_id": 4}

    def tick(self):
        self.index += 1
        return {"frame": 1000 + self.index, "time_s": 100 + self.index / 20}

    def read_activity(self, frame):
        i = frame - 1000
        if i != self.index:
            raise ValueError("fake tick mismatch")
        variant = self.case_id.removeprefix(ASSIGNMENT + "__")
        passenger = ((260 <= i < 400 and variant in ("passenger_active_stop", "ordinance_passenger_authorized")) or
                     (500 <= i < 600 and variant == "passenger_wait_stand") or
                     (400 <= i < 520 and variant == "passenger_driver_exit_park"))
        goods = ((240 <= i < 500 and variant == "goods_active_load") or
                 (240 <= i < 320 or 440 <= i < 520) and variant == "goods_wait_interrupted")
        return {"frame": frame, "time_s": 100 + i / 20,
                "source_kind": "original_native", "case_id": self.case_id,
                "ego_vehicle_id": 1, "passenger_actor_id": 2,
                "goods_actor_id": 3, "driver_actor_id": 4,
                "ego_speed_mps": 0.0 if 200 <= i < 560 else 1.0,
                "ego_xy_m": [float(min(i, 450) / 10), 0.0],
                "in_business_alley": True,
                "ordinance_reviewed_applicable": variant == "ordinance_passenger_authorized",
                "passenger_contact": passenger,
                "goods_contact": goods,
                "driver_in_vehicle": not (280 <= i < 460 and variant == "passenger_driver_exit_park"),
                "door_open": 250 <= i < 410}

    def read_cameras(self, frame):
        result = {name: {"frame": frame, "time_s": 100 + self.index / 20,
                         "png": PNG} for name in module.CAMERAS}
        if self.missing_camera:
            del result["reference_corner"]
        return result

    def brake(self):
        pass

    def cleanup(self):
        self.cleaned = True


class AcquisitionTests(unittest.TestCase):
    case_id = ASSIGNMENT + "__passenger_active_stop"

    def setUp(self):
        self.scratch = Path(".runtime-work/c378707-acquisition-tests").resolve()
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.previous = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(self.scratch)

    def tearDown(self):
        if self.previous is None:
            del os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]
        else:
            os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = self.previous

    def test_original_capture_keeps_native_and_relative_ticks(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as temp:
            out = Path(temp) / "attempt"
            operator = FakeOperator(self.case_id)
            result = module.capture(operator, self.case_id, out)
            self.assertTrue(operator.cleaned)
            self.assertEqual(result["frame_count"], 900)
            self.assertEqual(result["intervals_s"]["passenger_contact"], [[13.0, 20.0]])
            self.assertEqual(result["intervals_s"]["halt"], [[10.0, 28.0]])
            self.assertEqual(result["legal_conclusion"], "unreviewed")
            self.assertTrue((out / "activity-seal.json").is_file())
            self.assertTrue((out / "reference_corner.zip").is_file())
            self.assertEqual(audit(out, self.case_id)["structural_status"], "passed")
            checked, measured = measure_business_alley(out, self.case_id)
            self.assertEqual(checked["activity_sha256"], measured["history_sha256"])
            self.assertEqual(measured["intervals_s"]["halt"], [[10.0, 28.0]])
            with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                audit(out, self.case_id, require_native_attestation=True)
            (out / "approach.zip").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "camera source hash"):
                audit(out, self.case_id)
            with self.assertRaisesRegex(ValueError, "replace"):
                module.capture(FakeOperator(self.case_id), self.case_id, out)

    def test_missing_camera_fails_closed(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as temp:
            out = Path(temp) / "attempt"
            operator = FakeOperator(self.case_id, missing_camera=True)
            with self.assertRaisesRegex(ValueError, "camera"):
                module.capture(operator, self.case_id, out)
            self.assertTrue(operator.cleaned)
            self.assertFalse(out.exists())

    def test_runner_binds_reviewed_source_content(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as temp:
            folder = Path(temp)
            source = folder / "jurisdiction.json"
            source.write_text('{"reviewed":true}\n')
            packet = {"reviewed_sources": {"jurisdiction": {
                "path": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}}
            _verify_site_sources(packet, folder / "site.json")
            source.write_text('{"reviewed":false}\n')
            with self.assertRaisesRegex(ValueError, "hash differs"):
                _verify_site_sources(packet, folder / "site.json")

    def test_all_five_source_bound_comparisons_and_negative_fixed_source(self):
        with tempfile.TemporaryDirectory(dir=self.scratch) as temp:
            outputs = {}
            variants = {name for pair in PAIRS.values() for name in pair}
            for variant in variants:
                case_id = ASSIGNMENT + "__" + variant
                outputs[variant] = Path(temp) / variant
                module.capture(FakeOperator(case_id), case_id, outputs[variant])
            for comparison_id, (first, second) in PAIRS.items():
                with self.subTest(comparison_id=comparison_id):
                    self.assertEqual(compare(comparison_id, outputs[first], outputs[second])["structural_status"], "passed")
            altered = Path(temp) / "changed-frontage"
            module.capture(FakeOperator(ASSIGNMENT + "__passenger_wait_stand", business_sha="c" * 64),
                           ASSIGNMENT + "__passenger_wait_stand", altered)
            with self.assertRaisesRegex(ValueError, "fixed reviewed source differs"):
                compare("passenger_active_vs_waiting", outputs["passenger_active_stop"], altered)


if __name__ == "__main__":
    unittest.main()
