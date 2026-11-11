import copy
import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from build_branch_sites import check_branch, construct
from site_construction import load_site


class CrestBranchConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads((PACKAGE / "diagnostic-site-crest-short.json").read_text())

    def test_both_placements_and_approach_directions_have_distinct_rays(self):
        for placement in ("near_summit", "approach_to_crest"):
            for direction in ("approach_a", "approach_b"):
                with self.subTest(placement=placement, direction=direction):
                    site = construct(self.base, placement, direction)
                    proof = check_branch(site, placement, direction)
                    self.assertEqual(proof["planned_ray_crossings"][direction], True)
                    opposite = "approach_b" if direction == "approach_a" else "approach_a"
                    self.assertEqual(proof["planned_ray_crossings"][opposite], False)
                    self.assertEqual(proof["turn_site_to_summit_m"],
                                     40 if placement == "approach_to_crest" else 0)
                    for stations in proof["approach_stations_m"].values():
                        self.assertGreaterEqual(stations[-1], 152.4)

    def test_wrong_geometry_and_unreviewed_native_status_are_rejected(self):
        site = construct(self.base, "approach_to_crest", "approach_b")
        wrong = copy.deepcopy(site)
        wrong["occluder"]["center_xyz_m"][1] = 20
        with self.assertRaisesRegex(ValueError, "does not intersect"):
            check_branch(wrong, "approach_to_crest", "approach_b")
        with self.assertRaisesRegex(ValueError, "Wrong crest placement"):
            check_branch(site, "near_summit", "approach_b")
        source = PACKAGE / "branch-sites" / "approach_to_crest__occluded_approach_b.json"
        import hashlib
        with self.assertRaisesRegex(ValueError, "Diagnostic geometry"):
            load_site(source, hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
