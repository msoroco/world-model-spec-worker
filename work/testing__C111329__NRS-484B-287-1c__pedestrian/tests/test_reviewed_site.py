import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import CASES
from reviewed_site import REQUIRED_REVIEWS, load_reviewed_site
import test_site_geometry


class ReviewedSiteTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_site_geometry.CrossingSiteTests("test_unmarked_and_marked_comparison")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = Path(self.fixture.tmp.name)
        self.case_id = next(iter(CASES))
        self.packet = copy.deepcopy(self.fixture.packet)
        self.packet.update(cell_id="C111329", case_id=self.case_id)
        packet_path = self.root / "site-packet.json"
        packet_path.write_text(json.dumps(self.packet))
        xodr = self.root / "road.xodr"
        xodr.write_text('<OpenDRIVE><junction id="west"/><junction id="east"/></OpenDRIVE>')
        refs = {"packet": self.ref(packet_path), "opendrive": self.ref(xodr)}
        for name in REQUIRED_REVIEWS:
            source = self.root / (name + ".json")
            source.write_text(json.dumps({"fixture_only": True, "topic": name}))
            refs[name] = self.ref(source)
        self.review = {"format": "reviewed-c111329-between-intersections-site",
            "cell_id": "C111329", "case_id": self.case_id,
            "reviewer": "fixture reviewer", "method": "CPU source binding fixture only",
            "sources": refs}
        self.review_path = self.root / "review.json"
        self.save_review()

    @staticmethod
    def ref(path):
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def save_review(self):
        self.review_path.write_text(json.dumps(self.review))

    def test_source_bound_exact_site_and_unresolved_legal_findings(self):
        result = load_reviewed_site(self.review_path, expected_case_id=self.case_id)
        self.assertEqual(result["site"]["between_junction_ids"], ["west", "east"])
        self.assertEqual(result["legal_official_status"], "undetermined")
        self.assertEqual(result["nrs_484b_290_exception"], "undetermined")

    def test_missing_original_review_source_and_hash_drift_rejected(self):
        self.review["sources"].pop("device_authority")
        self.save_review()
        with self.assertRaisesRegex(ValueError, "inventory incomplete"):
            load_reviewed_site(self.review_path, expected_case_id=self.case_id)
        self.review["sources"]["device_authority"] = self.ref(self.root / "device_authority.json")
        self.save_review()
        (self.root / "device_authority.json").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            load_reviewed_site(self.review_path, expected_case_id=self.case_id)

    def test_wrong_case_or_missing_two_junction_map_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact fixed-cell"):
            load_reviewed_site(self.review_path, expected_case_id=list(CASES)[1])
        xodr = self.root / "road.xodr"
        xodr.write_text('<OpenDRIVE><junction id="west"/></OpenDRIVE>')
        self.review["sources"]["opendrive"] = self.ref(xodr)
        self.save_review()
        with self.assertRaisesRegex(ValueError, "two-junction"):
            load_reviewed_site(self.review_path, expected_case_id=self.case_id)


if __name__ == "__main__":
    unittest.main()
