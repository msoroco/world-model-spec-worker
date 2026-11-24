import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from reverse_alternative_comparison import ASSIGNMENT, SUFFIXES, audit
from test_reverse_alternatives import write_case


def make_attempt(root, alternative, *, expected_entry):
    root.mkdir()
    suffix = SUFFIXES[alternative][0 if expected_entry else 1]
    case_id = ASSIGNMENT + "__" + suffix
    region = ([[8, -3], [12, -3], [12, 3], [8, 3]]
              if alternative == "intersection" else
              [[-2, -10], [11, -10], [11, 2], [-2, 2]])
    start_body = [[15.5, -.5], [16.5, -.5], [16.5, .5], [15.5, .5]]
    if expected_entry:
        centers = [(16 - min(i, 8), 0) for i in range(900)]
        headings = [0] * 900
        if alternative == "street_corner":
            headings = [0 if i < 7 else 45 for i in range(900)]
    else:
        centers = [(16 - min(i, 2), 0) for i in range(900)]
        headings = [0] * 900
    write_case(root, alternative, body_centers=centers, headings=headings)
    context = json.loads((root / "reverse_site_context.json").read_text())
    context["expected_entry"] = expected_entry
    context["intersection_polygon_xy_m" if alternative == "intersection"
            else "street_corner_region_xy_m"] = region
    site_name = alternative + ("_site.json" if expected_entry else "_stop_site.json")
    source_keys = ("geometry_source", "camera_source", "road_topology_source")
    site = {"alternative": alternative, "expected_entry": expected_entry,
            "native_map_id": "native-signed-site", "road_id": 7,
            "region_polygon_xy_m": region, "vehicle_blueprint_id": "vehicle.audi.tt",
            "start_transform": {"x": 16, "y": 0, "z": .3, "yaw_deg": 0},
            "start_body_vertices_xy_m": start_body,
            "route_xy_m": [[16, 0], [15, 0], [10 if expected_entry else 14, 0]]}
    for key in source_keys:
        site[key] = context[key]
    (root / site_name).write_text(json.dumps(site) + "\n")
    context["site_packet_source"] = {
        "path": site_name,
        "sha256": hashlib.sha256((root / site_name).read_bytes()).hexdigest()}
    (root / "reverse_site_context.json").write_text(json.dumps(context) + "\n")
    config = {"selected_case_id": case_id, "law_id": "NRS-484B-113-2",
              "cell_id": "C215286", "actor": "motor_vehicle_driver",
              "rate_hz": 20, "duration_s": 45,
              "cameras": [{"name": name} for name in
                          ("overview", "approach", "reference_corner", "driver_reference")],
              "required_atoms": ["kin.position", "kin.heading"],
              "supported_case_ids": [ASSIGNMENT + "__" + item for item in SUFFIXES[alternative]]}
    (root / "config.json").write_text(json.dumps(config) + "\n")
    return root


class ComparisonTests(unittest.TestCase):
    def test_intersection_pair_and_changed_fixed_site(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            positive = make_attempt(root / "positive", "intersection", expected_entry=True)
            stop = make_attempt(root / "stop", "intersection", expected_entry=False)
            receipt = audit(positive, stop, "intersection")
            self.assertEqual(receipt["original_frames_per_case"], 900)
            self.assertFalse(receipt["physical_acceptance_claimed"])
            site_path = stop / "intersection_stop_site.json"
            site = json.loads(site_path.read_text())
            site["road_id"] = 99
            site_path.write_text(json.dumps(site) + "\n")
            context_path = stop / "reverse_site_context.json"
            context = json.loads(context_path.read_text())
            context["site_packet_source"]["sha256"] = hashlib.sha256(site_path.read_bytes()).hexdigest()
            context_path.write_text(json.dumps(context) + "\n")
            with self.assertRaisesRegex(ValueError, "fixed site condition differs"):
                audit(positive, stop, "intersection")

    def test_corner_pair_requires_observed_turn(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            positive = make_attempt(root / "positive", "street_corner", expected_entry=True)
            stop = make_attempt(root / "stop", "street_corner", expected_entry=False)
            receipt = audit(positive, stop, "street_corner")
            self.assertEqual(receipt["alternative"], "street_corner")
            history = positive / "reverse_history.jsonl"
            rows = [json.loads(row) for row in history.read_text().splitlines()]
            for row in rows:
                row["heading_deg"] = 0
            history.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "heading did not change"):
                audit(positive, stop, "street_corner")


if __name__ == "__main__":
    unittest.main()
