"""CPU checks for City sidewalk source gates and real construction calls."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from sidewalk_030 import CASES, construct, inside, measure_original, original_site, overlaps


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def spawn_device(self, position, blueprint):
        self.calls.append(("spawn", position, blueprint))
        return "device"

    def set_route(self, device, route):
        self.calls.append(("route", device, route))

    def set_conduct(self, device, conduct, operator):
        self.calls.append(("conduct", device, conduct, operator))

    def set_site(self, device, sidewalks, road, municipality):
        self.calls.append(("site", device, municipality))


class SidewalkTests(unittest.TestCase):
    def test_case_isolation_and_construction(self):
        from build_package import source_site
        for case in CASES:
            site = source_site(case)
            adapter = FakeAdapter()
            result = construct(adapter, site, case)
            self.assertEqual(result["legal_verdict"], None)
            self.assertEqual([x[0] for x in adapter.calls], ["spawn", "route", "conduct", "site"])
            polygon = site["road_polygon_xy"] if case.surface == "road" else site["sidewalk_polygons_xy"][case.side]
            self.assertTrue(all(inside(p, polygon) for p in site["ego_route_xy"]))
            self.assertEqual(site["municipality"], case.municipality)

    def test_unreviewed_packet_rejected(self):
        from build_package import source_site
        scratch = HERE.parents[1] / ".runtime-work" / "c412982-lvmc030-owner" / "tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            p = Path(temp) / "site.json"
            p.write_text(json.dumps(source_site(CASES[0])))
            with self.assertRaisesRegex(ValueError, "reviewed original"):
                original_site(p, CASES[0])

    def test_history_requires_source_join(self):
        from build_package import source_site
        site = source_site(CASES[0])
        row = {"original_frame": 1, "time_s": 1.0, "position_xy": [100, 1.5],
               "body_polygon_xy": [[99.6, 1.1], [100.4, 1.1], [100.4, 1.9], [99.6, 1.9]],
               "mounted_riding_source": True,
               "municipality_source_sha256": site["municipal_boundary_source_sha256"],
               "operator_source_sha256": site["operator_conduct_source_sha256"],
               "device_id": site["device"]["device_id"],
               "operator_id": site["operator_conduct"]["operator_id"],
               "device_source_sha256": site["device_specification_source_sha256"]}
        self.assertEqual(measure_original([row], site, CASES[0])["sidewalk_body_overlap_frames"], 1)
        row["device_source_sha256"] = "stale"
        with self.assertRaisesRegex(ValueError, "device or conduct"):
            measure_original([row], site, CASES[0])

    def test_body_overlap_excludes_collinear_disjoint_edges(self):
        left = [[0, 0], [1, 0], [1, 1], [0, 1]]
        right = [[2, 0], [3, 0], [3, 1], [2, 1]]
        touching = [[1, 0], [2, 0], [2, 1], [1, 1]]
        self.assertFalse(overlaps(left, right))
        self.assertTrue(overlaps(left, touching))


if __name__ == "__main__":
    unittest.main()
