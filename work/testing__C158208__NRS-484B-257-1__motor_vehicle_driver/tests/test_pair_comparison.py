import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_source_tick_capture import GEOMETRY, CONTEXT, body, capture


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pair_comparison import ASSIGNMENT, CASES, audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_attempt(root, case, *, speed, site="a" * 64, context=None, through_offset=0,
                 geometry=None):
    attempt = root / case.rsplit("__", 1)[-1]
    writer = capture.TickCapture(attempt, geometry or GEOMETRY, context or CONTEXT)
    for index, x in enumerate((-9, -5, 0, 5, 13)):
        y = (-8, -3, 4, 4, 12)[index] + through_offset
        writer.append({"frame": 400 + index, "time_s": index * .05,
            "ego": {"body_vertices_xy_m": body(x, 5), "velocity_xy_mps": [speed, 0]},
            "through_vehicle": {"center_xy_m": [5, y], "body_vertices_xy_m": body(5, y)},
            "visibility_probe": {"source": "native_raycast", "occluded": index == 0,
                                 "origin_xy_m": [x, 5], "target_xy_m": [5, y]},
            "sign_present": True})
    writer.close()
    identity = {"format": "c158208-original-capture-identity-v1",
                "assignment_id": ASSIGNMENT, "case_id": case,
                "construction_sha256": "c" * 64, "site_packet_sha256": site,
                "map_opendrive_sha256": "b" * 64,
                "original_tick_seal_sha256": sha(writer.seal_path),
                "provenance_kind": "synthetic_fixture"}
    (attempt / "capture-identity.json").write_text(json.dumps(identity, sort_keys=True) + "\n")
    return attempt


class PairComparisonTests(unittest.TestCase):
    def test_pair_source_bound_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = make_attempt(root, CASES[0], speed=1)
            second = make_attempt(root, CASES[1], speed=3)
            result = audit(first, second, diagnostic=True)
            self.assertEqual(result["status"], "diagnostic_fixture_only")
            self.assertFalse(result["video_accepted"])
            self.assertEqual(result["legal_status"], "unresolved")
            with self.assertRaisesRegex(ValueError, "exact reviewed case expectations"):
                audit(first, second)

    def test_rejects_case_swap_and_seal_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = make_attempt(root, CASES[0], speed=1)
            second = make_attempt(root, CASES[1], speed=3)
            with self.assertRaisesRegex(ValueError, "capture identity case differs"):
                audit(second, first, diagnostic=True)
            with (first / "nearest-view-tick-seal.json").open("a") as stream:
                stream.write(" ")
            with self.assertRaisesRegex(ValueError, "tick seal hash differs"):
                audit(first, second, diagnostic=True)

    def test_rejects_fixed_site_and_through_history_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = make_attempt(root, CASES[0], speed=1)
            second = make_attempt(root, CASES[1], speed=3, site="f" * 64)
            with self.assertRaisesRegex(ValueError, "fixed site_packet_sha256 differs"):
                audit(first, second, diagnostic=True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = make_attempt(root, CASES[0], speed=1)
            second = make_attempt(root, CASES[1], speed=3, through_offset=1)
            with self.assertRaisesRegex(ValueError, "through vehicle history differs"):
                audit(first, second, diagnostic=True)

    def test_rejects_missing_speed_separation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = make_attempt(root, CASES[0], speed=3)
            second = make_attempt(root, CASES[1], speed=3)
            with self.assertRaisesRegex(ValueError, "lower approach speed"):
                audit(first, second, diagnostic=True)

    def test_rejects_fixed_geometry_and_context_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = make_attempt(root, CASES[0], speed=1)
            shifted = dict(GEOMETRY, ego_route_origin_xy_m=[-11, 5])
            second = make_attempt(root, CASES[1], speed=3, geometry=shifted)
            with self.assertRaisesRegex(ValueError, "fixed intersection geometry differs"):
                audit(first, second, diagnostic=True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = make_attempt(root, CASES[0], speed=1)
            extra = dict(CONTEXT, site_review_note="second site")
            second = make_attempt(root, CASES[1], speed=3, context=extra)
            with self.assertRaisesRegex(ValueError, "fixed reviewed context differs"):
                audit(first, second, diagnostic=True)

    def test_original_mode_requires_reviewed_hashes_and_full_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = make_attempt(root, CASES[0], speed=1)
            second = make_attempt(root, CASES[1], speed=3)
            for attempt in (first, second):
                path = attempt / "capture-identity.json"
                identity = json.loads(path.read_text())
                identity["provenance_kind"] = "original_capture"
                path.write_text(json.dumps(identity, sort_keys=True) + "\n")
            expected = {case: {"construction_sha256": "c" * 64,
                               "site_packet_sha256": "a" * 64,
                               "map_opendrive_sha256": "b" * 64} for case in CASES}
            wrong = json.loads(json.dumps(expected))
            wrong[CASES[0]]["construction_sha256"] = "d" * 64
            with self.assertRaisesRegex(ValueError, "differs from reviewed expectation"):
                audit(first, second, reviewed_expectations=wrong)
            with self.assertRaisesRegex(ValueError, "900 contiguous"):
                audit(first, second, reviewed_expectations=expected)


if __name__ == "__main__":
    unittest.main()
