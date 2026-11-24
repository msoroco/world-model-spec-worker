import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("comparison_audit", ROOT / "comparison_audit.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(suffix, distance, merged=True):
    return {"native_map_sha256": "map", "highway_review_sha256": "highway", "lane_design_sha256": "lanes",
            "entry_route_sha256": "entry", "receiving_vehicle_route_sha256": "traffic", "camera_plan_sha256": "camera",
            "original_trace_source": "native/" + suffix + "/trace.json", "original_trace_sha256": suffix,
            "merge_observed": merged, "censored": not merged, "merge_frame": 200 if merged else None,
            "distance_ft": distance, "boundary_ft": 50.0}


def triple():
    return {"below_50ft": row("below", 49.1), "at_50ft": row("at", 50.0),
            "above_50ft": row("above", 51.2)}


class ComparisonTests(unittest.TestCase):
    def test_numeric_comparison_retains_actual_measurements(self):
        result = MODULE.audit_numeric_triple(triple())
        self.assertEqual(result["measured_distance_ft"]["above_50ft"], 51.2)
        self.assertIsNone(result["legal_judgment"])

    def test_rejects_missing_original_trace(self):
        p = triple()
        p["at_50ft"]["original_trace_sha256"] = None
        with self.assertRaisesRegex(ValueError, "missing original trace"):
            MODULE.audit_numeric_triple(p)

    def test_rejects_changed_receiving_traffic(self):
        p = triple()
        p["above_50ft"]["receiving_vehicle_route_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "receiving_vehicle_route"):
            MODULE.audit_numeric_triple(p)

    def test_rejects_censored_numeric_case(self):
        p = triple()
        p["below_50ft"]["merge_observed"] = False
        with self.assertRaisesRegex(ValueError, "observed merge"):
            MODULE.audit_numeric_triple(p)

    def test_rejects_unrealized_boundary_probe(self):
        p = triple()
        p["below_50ft"]["distance_ft"] = 50.2
        with self.assertRaisesRegex(ValueError, "below/at/above probes"):
            MODULE.audit_numeric_triple(p)
        p = triple()
        p["at_50ft"]["distance_ft"] = 50.4
        with self.assertRaisesRegex(ValueError, "below/at/above probes"):
            MODULE.audit_numeric_triple(p)
        p = triple()
        p["above_50ft"]["distance_ft"] = 49.8
        with self.assertRaisesRegex(ValueError, "below/at/above probes"):
            MODULE.audit_numeric_triple(p)

    def test_merge_comparison_requires_censoring(self):
        merged = row("below", 49.1)
        no_merge = row("no_merge", 62.0, False)
        self.assertIsNone(MODULE.audit_merge_observation(merged, no_merge)["legal_judgment"])
        no_merge["merge_frame"] = 250
        with self.assertRaisesRegex(ValueError, "censored"):
            MODULE.audit_merge_observation(merged, no_merge)


if __name__ == "__main__":
    unittest.main()
