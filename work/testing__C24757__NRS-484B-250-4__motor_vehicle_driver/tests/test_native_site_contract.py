import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "native_site_contract", Path(__file__).resolve().parents[1] / "native_site_contract.py")
site_contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_contract)


def write_bound(root, name, value):
    path = root / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class SiteTests(unittest.TestCase):
    def fixture(self, root, kind="stop_line"):
        site = {"native_map_name": "DiagnosticTown", "intersection_id": 6,
                "native_signal_id": 13, "installed_uncovered_vehicular_heads": True,
                "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]],
                "entrance_road_lanes": [[1, -1], [2, -1]],
                "stop_line_exists": kind == "stop_line",
                "crosswalk_exists": kind == "crosswalk",
                "stop_boundary": {"kind": kind, "source": "map-and-original-front-view",
                                  "point_xy_m": [0, 0], "upstream_normal_xy": [-1, 0]},
                "approach_visibility_source": "native-map-and-front-view"}
        docs = {}
        for role, fields in site_contract.SOURCE_CLAIMS.items():
            document = {"format": "worker-inoperative-junction-source", "source_role": role,
                        "review_basis": "synthetic CPU fixture only",
                        "reviewed_site_fields": {field: site[field] for field in fields}}
            docs[role] = write_bound(root, role + ".json", document)
        review = {"format": "worker-inoperative-junction-review",
                  "review_status": "reviewed_candidate", "site": site, "source_documents": docs}
        config = {"site": site, "site_review": write_bound(root, "review.json", review)}
        return config

    def test_three_stopping_reference_branches(self):
        for kind in ("stop_line", "crosswalk", "nearest_view"):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config = self.fixture(root, kind)
                receipt = site_contract.validate_site(config, root)
                self.assertEqual(receipt["selected_boundary"], kind)
                self.assertFalse(receipt["native_site_verified"])

    def test_rejects_tampered_source_and_unsourced_boundary_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.fixture(root)
            document = root / "signal_heads.json"
            document.write_text(document.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "source missing or changed"):
                site_contract.validate_site(config, root)
            config = self.fixture(root)
            config["site"]["stop_line_exists"] = False
            with self.assertRaisesRegex(ValueError, "differs from bound review packet"):
                site_contract.validate_site(config, root)
            config = self.fixture(root)
            config["site_review"]["path"] = "../review.json"
            with self.assertRaisesRegex(ValueError, "escapes packet root"):
                site_contract.validate_site(config, root)


if __name__ == "__main__":
    unittest.main()
