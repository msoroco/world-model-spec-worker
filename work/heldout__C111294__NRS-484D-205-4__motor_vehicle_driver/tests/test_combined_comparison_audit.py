import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combined_comparison_audit import audit


HERE = Path(__file__).resolve().parents[1]


class CombinedComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.separate, self.combined = root/'separate', root/'combined'
        for path, specification in ((self.separate, 'diagnostic-input.json'),
                                    (self.combined, 'diagnostic-combined.json')):
            path.mkdir()
            source = json.loads((HERE/specification).read_text())['files']
            for name in ('equipment.json', 'asset-inspection.json', 'motion.jsonl',
                         'other_vehicle.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                         'intersection_context.json'):
                if name in source:
                    (path/name).write_text(source[name])
        (self.separate/'config.json').write_text((HERE/'config.json').read_text())
        construction = json.loads((HERE/'cases/forward_combined_backup_lamp_off/'
                                   'primary-construction.json').read_text())
        config = next(item['content'] for item in construction['files']
                      if item['path'] == 'config.json')
        (self.combined/'config.json').write_text(config)

    def test_source_bound_separate_combined_difference(self):
        result = audit(self.separate, self.combined)
        self.assertTrue(result['fixed_conditions_checked'])
        self.assertEqual(result['shared_housing_ids'], ['rear-combined-1'])
        self.assertFalse(result['actual_pixels_reviewed'])

    def test_rejects_changed_fixed_context_and_missing_inspection(self):
        context = json.loads((self.combined/'intersection_context.json').read_text())
        context['other_vehicle_purpose'] = 'changed'
        (self.combined/'intersection_context.json').write_text(json.dumps(context))
        with self.assertRaisesRegex(ValueError, 'Fixed original comparison source'):
            audit(self.separate, self.combined)
        (self.combined/'intersection_context.json').write_text(
            (self.separate/'intersection_context.json').read_text())
        (self.combined/'asset-inspection.json').unlink()
        with self.assertRaises((FileNotFoundError, ValueError)):
            audit(self.separate, self.combined)


if __name__ == '__main__':
    unittest.main()
