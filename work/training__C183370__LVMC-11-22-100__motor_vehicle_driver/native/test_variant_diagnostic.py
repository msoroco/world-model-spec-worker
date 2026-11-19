import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_variant_diagnostic import variant
from variant_analyze import analyze_rows


class VariantDiagnosticTest(unittest.TestCase):
    def test_barrier_pair_has_distinct_contact_with_explicit_synthetic_sources(self):
        for route, expected_count in (('crossing', 300), ('avoidance', 0)):
            spec = variant(route)
            files = spec['files']
            frames = [json.loads(row) for row in files['video_frames.jsonl'].splitlines()]
            actors = [json.loads(row) for row in files['native-actors.jsonl'].splitlines()]
            readback = json.loads(files['live-readback.json'])
            observed = analyze_rows(frames, actors, readback, diagnostic=True)
            self.assertEqual(len(observed['pavement_footprint_contact_frames']), expected_count)
            self.assertEqual(len(spec['videos']), 4)
            self.assertEqual(observed['source_frames'], 600)
            self.assertEqual(json.loads(files['capture-receipt.json'])['case'], route)
            self.assertFalse(json.loads(files['acquisition-provenance.json'])['native_executed'])


if __name__ == '__main__':
    unittest.main()
