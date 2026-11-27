"""CPU proof of source gating, Native calls, geometry, and negative cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))

from highway_scene_construction import ASSIGNMENT, SOURCE_FIELDS, construct, validate_site
from highway_observations import inside, observe, sha

CASE = ASSIGNMENT + "__park_narrow_device"


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def site_packet(directory):
    records = {}
    site = {"assignment_id": ASSIGNMENT, "cell_id": "C412262",
            "source_kind": "original_reviewed_highway_site", "review_status": "reviewed",
            "highway_width_variant": "narrow", "device_variant": "erected_applicable",
            "parking_location_variant": "on_highway", "lane_route_xy_m": [[0, 0], [20, 0]],
            "highway_boundary_xy_m": [[0, -4], [20, -4], [20, 4], [0, 4]],
            "device_extent_xy_m": [[0, -3], [20, -3], [20, 3], [0, 3]],
            "full_highway_width_profile_m": [8.0, 8.0],
            "device": {"blueprint_id": "static.prop.no_parking", "exact_instruction_text": "No Parking",
                       "erecting_authority_id": "reviewed-authority", "conformity_source_id": "reviewed-standard",
                       "governing_extent_id": "reviewed-extent"}}
    for field in SOURCE_FIELDS:
        target = directory / (field + ".txt")
        target.write_text("DIAGNOSTIC ONLY " + field + "\n")
        digest = sha(target)
        site[field] = digest
        records[field] = {"path": target.name, "sha256": digest}
    site["source_records"] = records
    path = directory / "reviewed-site.json"
    write(path, site)
    return path


class Adapter:
    def __init__(self):
        self.events = []
        self.site = None

    def configure_highway(self, route, boundary, width):
        self.events.append("configure")
        self.boundary, self.width = boundary, width

    def read_highway(self):
        self.events.append("read_highway")
        return {"boundary_xy_m": self.boundary, "width_profile_m": self.width}

    def spawn_device(self, device):
        self.events.append("spawn_device")
        self.device = device
        return "device"

    def read_device(self):
        self.events.append("read_device")
        return dict(self.device, state="erected_applicable")

    def spawn_vehicle(self, point):
        self.events.append("spawn_vehicle")
        return "vehicle"

    def drive_to_parking_location(self, vehicle, place, route):
        self.events.append("drive")
        self.place = place

    def hold_for_activity(self, vehicle, activity):
        self.events.append("hold")
        self.activity = activity

    def read_vehicle_state(self, vehicle):
        self.events.append("read_vehicle")
        return {"activity_request": self.activity}

    def destroy(self, actor):
        self.events.append("destroy_" + actor)


class HighwayTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = site_packet(self.root)

    def test_source_gated_native_construction(self):
        adapter = Adapter()
        result = construct(adapter, self.site, CASE)
        self.assertEqual(result["owned"], ("device", "vehicle"))
        self.assertEqual(adapter.events, ["configure", "read_highway", "spawn_device",
                                          "read_device", "spawn_vehicle", "drive", "hold", "read_vehicle"])
        self.assertEqual(adapter.place, "on_highway")

    def test_missing_source_and_wrong_intervention_rejected(self):
        site = json.loads(self.site.read_text())
        (self.root / site["source_records"]["device_authority_sha256"]["path"]).unlink()
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            validate_site(self.site, CASE)
        site_packet(self.root)
        site = json.loads(self.site.read_text())
        site["device_variant"] = "absent"
        write(self.site, site)
        with self.assertRaisesRegex(ValueError, "differs from exact case"):
            validate_site(self.site, CASE)

    def test_full_body_geometry_and_negative_trace(self):
        self.assertTrue(inside((5, 0), [[0, -4], [20, -4], [20, 4], [0, 4]]))
        self.assertFalse(inside((5, 5), [[0, -4], [20, -4], [20, 4], [0, 4]]))
        context = json.loads(self.site.read_text())
        reviewed = self.root / "reviewed-source"
        reviewed.mkdir()
        shutil.copyfile(self.site, reviewed / "reviewed-site.json")
        for record in context["source_records"].values():
            shutil.copyfile(self.root / record["path"], reviewed / record["path"])
        context.update({"case_id": CASE, "highway_width_request": "narrow",
                        "device_request": "erected_applicable", "activity_request": "park",
                        "parking_location_request": "on_highway",
                        "site_sha256": sha(reviewed / "reviewed-site.json")})
        context_path = self.root / "context.json"
        write(context_path, context)
        trace = self.root / "trace.jsonl"
        rows = [{"frame": i, "time_s": i / 20, "vehicle_body_polygon_xy_m":
                 [[5, -1], [7, -1], [7, 1], [5, 1]], "speed_mps": 0.0} for i in range(9)]
        trace.write_text("".join(json.dumps(r) + "\n" for r in rows))
        receipt = self.root / "receipt.json"
        write(receipt, {"assignment_id": ASSIGNMENT, "case_id": CASE,
                        "source_kind": "original_native_capture",
                        "context_sha256": sha(context_path), "trace_sha256": sha(trace), "frame_count": 9})
        report = observe(CASE, context_path, trace, receipt)
        self.assertTrue(all(sample["body_on_highway"] for sample in report["samples"]))
        self.assertEqual(report["narrow_highway_judgment"], "unresolved")
        rows[0]["vehicle_body_polygon_xy_m"] = [[5, 4.5], [7, 4.5], [7, 5], [5, 5]]
        trace.write_text("".join(json.dumps(r) + "\n" for r in rows))
        with self.assertRaisesRegex(ValueError, "seal mismatch"):
            observe(CASE, context_path, trace, receipt)
        write(receipt, {"assignment_id": ASSIGNMENT, "case_id": CASE,
                        "source_kind": "original_native_capture",
                        "context_sha256": sha(context_path), "trace_sha256": sha(trace), "frame_count": 9})
        self.assertFalse(observe(CASE, context_path, trace, receipt)["samples"][0]["body_on_highway"])
        (reviewed / "reviewed-site.json").unlink()
        with self.assertRaisesRegex(ValueError, "reviewed highway source packet missing"):
            observe(CASE, context_path, trace, receipt)


if __name__ == "__main__":
    unittest.main()
