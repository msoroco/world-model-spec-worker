"""CPU tests of oncoming geometry and actual adapter construction calls."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from beam_construction import construct, validate_site

ROOT = Path(__file__).resolve().parent
TEMP_ROOT = ROOT.parents[1] / ".runtime-work" / "c230259-construction-tests"
PLAN = json.loads((ROOT / "case-plan.json").read_text())
CASES = {x["case_id"].rsplit("__", 1)[-1]: x for x in PLAN["cases"]}


class Actor:
    def __init__(self, identifier):
        self.id = identifier


class Adapter:
    def __init__(self):
        self.calls = []

    def spawn_vehicle(self, blueprint, point):
        self.calls.append(("vehicle", blueprint, point))
        return Actor(len(self.calls))

    def set_route(self, actor, route):
        self.calls.append(("route", actor.id, route))

    def spawn_target(self, blueprint, point):
        self.calls.append(("target", blueprint, point))
        return Actor(len(self.calls))

    def set_beam(self, actor, beam):
        self.calls.append(("beam", actor.id, beam))

    def spawn_camera(self, view, spec, attach_to):
        self.calls.append(("camera", view, attach_to.id))
        return Actor(len(self.calls))


def site_for(root: Path, case: dict):
    source = root / "original-map.xodr"
    source.write_text("reviewed OpenDRIVE source\n")
    feet = case["requested_start_separation_ft"] or 1400
    separation = feet * .3048
    return {"format": "beam-road-site-v1", "case_id": case["case_id"],
            "cell_id": "C230259", "actor": "motor_vehicle_driver",
            "diagnostic_fixture": True, "source_refs": [{"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
            "map_name": "diagnostic-road", "map_sha256": "b" * 64,
            "requested_beam": case["requested_beam"],
            "requested_contour": case["requested_contour"],
            "requested_load": case["requested_load"],
            "requested_start_separation_ft": case["requested_start_separation_ft"],
            "routes": {"ego": [[0, 0, 0], [100, 0, 0]],
                       "oncoming": [[separation, 0, 0], [separation - 100, 0, 0]]},
            "highway_or_shoulder_polygon_xy_m": [[-10, -5], [250, -5], [250, 5], [-10, 5]],
            "targets": {"person": {"blueprint_id": "walker.pedestrian.0001", "transform_m": [45, 1, 0]},
                        "vehicle": {"blueprint_id": "vehicle.audi.a2", "transform_m": [75, 1, 0]}},
            "blueprints": {"ego": "vehicle.audi.a2", "oncoming": "vehicle.tesla.model3"},
            "driver_eye_offsets_m": {"ego": [0.2, 0.0, 1.4], "oncoming": [0.2, 0.0, 1.4]},
            "speed_requests_mps": {"ego": 2.0, "oncoming": 2.0},
            "cameras": {view: {"blueprint_id": "sensor.camera.rgb", "transform_m": [0, 0, 2], "fov_deg": 20 if view == "driver_reference" else 90}
                        for view in ("overview", "approach", "reference_corner", "driver_reference")}}


class BeamConstructionTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="site-", dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _write(self, case, site):
        path = self.root / "site.json"
        path.write_text(json.dumps(site) + "\n")
        return path

    def test_all_exact_case_geometries_and_creation_calls(self):
        for case in PLAN["cases"]:
            site = site_for(self.root, case)
            path = self._write(case, site)
            validated = validate_site(path, case, diagnostic=True)
            adapter = Adapter()
            result = construct(adapter, validated, case=case)
            self.assertEqual(len(result["actor_ids"]), 4)
            self.assertEqual(len(result["camera_ids"]), 4)
            self.assertEqual(len([x for x in adapter.calls if x[0] == "route"]), 2)
            self.assertEqual(len([x for x in adapter.calls if x[0] == "camera"]), 4)
            self.assertEqual([x for x in adapter.calls if x[0] == "beam"][0][-1], case["requested_beam"])

    def test_same_direction_route_rejected(self):
        case = CASES["oncoming_499_low"]
        site = site_for(self.root, case)
        site["routes"]["oncoming"][-1] = [300, 0, 0]
        with self.assertRaisesRegex(ValueError, "oppose"):
            validate_site(self._write(case, site), case, diagnostic=True)

    def test_500_foot_target_mismatch_rejected(self):
        case = CASES["oncoming_500_low"]
        site = site_for(self.root, case)
        site["routes"]["oncoming"][0][0] += 20
        with self.assertRaisesRegex(ValueError, "separation"):
            validate_site(self._write(case, site), case, diagnostic=True)

    def test_missing_original_source_rejected(self):
        case = CASES["oncoming_499_low"]
        site = site_for(self.root, case)
        site["source_refs"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash differs"):
            validate_site(self._write(case, site), case, diagnostic=True)

    def test_unreviewed_physical_packet_rejected(self):
        case = CASES["oncoming_499_low"]
        site = site_for(self.root, case)
        site["diagnostic_fixture"] = False
        with self.assertRaisesRegex(ValueError, "missing source review"):
            validate_site(self._write(case, site), case, diagnostic=False)


if __name__ == "__main__":
    unittest.main()
