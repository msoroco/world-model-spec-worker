import json
from pathlib import Path
import tempfile
import unittest

from runner import traversal_route
from traversal import check_pair, measure, synthetic_samples


class TraversalBundleProof(unittest.TestCase):
    def test_controlled_full_body_traversal(self):
        result = check_pair()
        self.assertEqual(result["cases"]["traversal_reference"]["moving_left_traversal_frames"],0)
        self.assertGreaterEqual(result["cases"]["traversal_contrast"]["moving_left_traversal_frames"],10)
        for case in ("traversal_reference","traversal_contrast"):
            self.assertEqual(len(traversal_route(case)),480)

    def test_source_bound_saved_measure_and_negative(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "rows.json"
            for case in ("traversal_reference","traversal_contrast"):
                rows = synthetic_samples(case)
                source.write_text(json.dumps(rows))
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                result = measure(rows,source,digest)
                self.assertEqual(result["moving_left_traversal_frames"],0 if case.endswith("reference") else 39)
                with self.assertRaisesRegex(ValueError,"hash"):
                    measure(rows,source,"0"*64)
                tampered = json.loads(source.read_text())
                tampered[333]["body_xy_m"][0][1] += 1
                with self.assertRaisesRegex(ValueError,"rows differ"):
                    measure(tampered,source,digest)


if __name__ == "__main__":
    unittest.main()
