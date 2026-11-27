"""Synthetic operator lifecycle proof; it does not establish physical completion."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from curb_geometry import ASSIGNMENT, SOURCES
from native_acquisition import CAMERAS, capture
from audit_original_attempt import audit
from audit_comparisons import PAIRS, compare
from analysis import build as build_analysis


class FakeOperator:
    def __init__(self, map_bytes, *, drop_camera=False, distance_inches=18, angle_deg=0, parked=True):
        self.map_bytes = map_bytes
        self.drop_camera = drop_camera
        self.distance_inches = distance_inches
        self.angle_deg = angle_deg
        self.parked = parked
        self.index = -1
        self.started = self.braked = self.cleaned = False

    def get_opendrive_bytes(self):
        return self.map_bytes

    def start(self, plan):
        self.started = True
        self.plan = plan

    def read_actor_inventory(self):
        return {"ego_vehicle_id": "ego-original-17", "actual_blueprint": "vehicle.test"}

    def tick(self):
        self.index += 1
        return {"frame": 100 + self.index, "time_s": 10 + self.index / 20}

    def read_right_wheels(self, frame):
        assert frame == 100 + self.index
        import math
        radians = math.radians(self.angle_deg)
        front_y = self.distance_inches * .0254
        rear_y = front_y - 2.7 * math.sin(radians)
        return {"frame": frame, "time_s": 10 + self.index / 20,
                "source_kind": "original_native", "ego_vehicle_id": "ego-original-17",
                "speed_mps": 0, "parking_brake_applied": self.parked,
                "right_front_wheel_xy_m": [2.7 * math.cos(radians), front_y],
                "right_rear_wheel_xy_m": [0, rear_y]}

    def read_cameras(self, frame):
        result = {name: {"frame": frame, "time_s": 10 + self.index / 20,
                         "png": b"\x89PNG\r\n\x1a\nsynthetic"} for name in CAMERAS}
        if self.drop_camera:
            result.pop("driver_reference")
        return result

    def brake(self):
        self.braked = True

    def cleanup(self):
        self.cleaned = True


class NativeAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + "__park_18in_parallel"
        self.map_bytes = b"synthetic native map"
        sources = {}
        for name in SOURCES:
            data = self.map_bytes if name == "native_opendrive_map" else ("source:" + name).encode()
            path = self.root / (name + ".source")
            path.write_bytes(data)
            sources[name] = {"path": path.name, "sha256": hashlib.sha256(data).hexdigest()}
        self.site = self.root / "site.json"
        self.site.write_text(json.dumps({
            "format": "worker-right-curb-site-v1", "case_id": self.case,
            "sources": sources,
            "reviewed_assertions": {"public_highway": True, "residence_district": True,
                                    "adjacent_right_curb": True, "ordinary_motor_vehicle": True,
                                    "right_side_default_branch": True,
                                    "left_curb_ordinance_applies": False,
                                    "angle_parking_ordinance_applies": False},
            "right_curb_xy_m": [[-10, 0], [10, 0]],
            "parking_route_xy_m": [[-8, 1], [8, 1]],
            "roadway_side_of_curb": "left",
            "reviewed_right_wheel_axle_spacing_m": 2.7,
            "reviewed_curb_station_m": 8}, sort_keys=True) + "\n")

    def test_original_readback_is_measured_and_owner_released(self):
        operator = FakeOperator(self.map_bytes)
        target = self.root / "attempt"
        measured = capture(operator, self.site, self.case, target, diagnostic=True)
        self.assertTrue(operator.started and operator.braked and operator.cleaned)
        self.assertAlmostEqual(measured["max_right_wheel_distance_inches"], 18)
        self.assertTrue(measured["diagnostic_fixture"])
        self.assertFalse(measured["physical_acceptance_claimed"])
        self.assertEqual(len((target / "original-attempt" / "wheel-motion.jsonl").read_text().splitlines()), 9)
        self.assertFalse(json.loads((target / "original-attempt" / "inventory.json").read_text())["physical_completion"])
        audited = audit(target, self.case)
        self.assertEqual(audited["structural_status"], "passed")
        (target / "config.json").write_text(json.dumps({"selected_case_id": self.case}) + "\n")
        analyzed = build_analysis(target)
        self.assertEqual(analyzed["measurements"]["curb_requirement_1"]["value"]["statutory_distance_inches"], 18)
        self.assertFalse(analyzed["legal_verdict_claimed"])
        with self.assertRaisesRegex(ValueError, "diagnostic fixture cannot attest"):
            audit(target, self.case, require_native_attestation=True)

    def test_full_duration_synthetic_readback_is_still_diagnostic(self):
        target = self.root / "full-duration-attempt"
        measured = capture(FakeOperator(self.map_bytes), self.site, self.case,
                           target, diagnostic=True, diagnostic_full_duration=True)
        self.assertEqual(len(measured["stopped_frames"]), 900)
        self.assertEqual(len(measured["parking_brake_frames"]), 900)
        self.assertEqual(audit(target, self.case)["frame_count"], 900)
        with self.assertRaisesRegex(ValueError, "diagnostic fixture cannot attest"):
            audit(target, self.case, require_native_attestation=True)

    def test_audit_rejects_stale_original_motion(self):
        target = self.root / "attempt"
        capture(FakeOperator(self.map_bytes), self.site, self.case, target, diagnostic=True)
        motion = target / "original-attempt" / "wheel-motion.jsonl"
        motion.write_text(motion.read_text().replace('"speed_mps":0', '"speed_mps":1', 1))
        with self.assertRaisesRegex(ValueError, "source hash differs: wheel-motion"):
            audit(target, self.case)

    def test_missing_original_camera_rejected_with_cleanup(self):
        operator = FakeOperator(self.map_bytes, drop_camera=True)
        target = self.root / "attempt"
        with self.assertRaisesRegex(ValueError, "four original cameras missing"):
            capture(operator, self.site, self.case, target, diagnostic=True)
        self.assertTrue(operator.braked and operator.cleaned)
        self.assertFalse(target.exists())

    def test_capture_seal_failure_still_releases_native_owner(self):
        class FailedGraph:
            def close(self, *, confirmed):
                raise ValueError("synthetic capture sealing failure")

        operator = FakeOperator(self.map_bytes)
        operator.pipeline_capture = FailedGraph()
        with self.assertRaisesRegex(ValueError, "capture sealing failure"):
            capture(operator, self.site, self.case, self.root / "attempt", diagnostic=True)
        self.assertTrue(operator.braked and operator.cleaned)

    def test_stale_original_map_rejected_before_start(self):
        operator = FakeOperator(b"different map")
        with self.assertRaisesRegex(ValueError, "OpenDRIVE differs"):
            capture(operator, self.site, self.case, self.root / "attempt", diagnostic=True)
        self.assertFalse(operator.started)

    def test_all_controlled_comparisons_and_changed_fixed_source(self):
        made = {}
        variants = {name for pair in PAIRS.values() for name in pair}
        for variant in variants:
            case = ASSIGNMENT + "__" + variant
            site_root = self.root / variant
            site_root.mkdir()
            for name in SOURCES:
                shutil.copy2(self.root / (name + ".source"), site_root / (name + ".source"))
            site_data = json.loads(self.site.read_text())
            site_data["case_id"] = case
            site = site_root / "site.json"
            site.write_text(json.dumps(site_data, sort_keys=True) + "\n")
            distance = 19 if "19in" in variant else 17 if "17in" in variant else 18
            operator = FakeOperator(self.map_bytes, distance_inches=distance,
                                    angle_deg=8 if "skew" in variant else 0,
                                    parked=variant.startswith("park"))
            attempt = self.root / ("attempt-" + variant)
            capture(operator, site, case, attempt, diagnostic=True)
            made[variant] = attempt
        for comparison_id, pair in PAIRS.items():
            result = compare(comparison_id, made[pair[0]], made[pair[1]])
            self.assertTrue(result["fixed_source_and_capture_checked"])
            self.assertFalse(result["physical_acceptance"])
        fallback = self.root / "attempt-boundary-fallback"
        capture(FakeOperator(self.map_bytes, distance_inches=18),
                self.root / "park_18in_parallel" / "site.json",
                ASSIGNMENT + "__park_18in_parallel", fallback,
                fallback=True, diagnostic=True)
        with self.assertRaisesRegex(ValueError, "fixed original capture context differs"):
            compare("inside_vs_boundary", made["park_17in_parallel"], fallback)
        changed = made["park_19in_parallel"] / "original-attempt" / "site.json"
        site_data = json.loads(changed.read_text())
        site_data["reviewed_assertions"]["residence_district"] = False
        changed.write_text(json.dumps(site_data) + "\n")
        with self.assertRaisesRegex(ValueError, "source hash differs: site"):
            compare("boundary_vs_outside", made["park_18in_parallel"], made["park_19in_parallel"])
