import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_queue_proposal import build
from comparison_audit import VARIABLES, audit
from school_uturn import CASES
from source_audit import audit as audit_sources
from test_school_uturn import rows, scene


class ComparisonAndQueueTests(unittest.TestCase):
    def write(self, directory, name, case):
        p = Path(directory) / (name + '.json')
        p.write_text(json.dumps({'case_id': case.name, 'original_recording_id': name,
                                 'scene': scene(case), 'frames': rows(case)}), encoding='utf-8')
        return p

    def test_all_five_controlled_comparisons(self):
        base = CASES[0]
        for name, target in zip(VARIABLES, CASES[1:]):
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                    dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as directory:
                left = self.write(directory, 'left', base)
                right = self.write(directory, 'right', target)
                self.assertTrue(audit(left, right, name)['fixed_geometry_and_states_checked'])

    def test_fixed_zone_and_undeclared_state_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as directory:
            left = self.write(directory, 'left', CASES[0])
            right = self.write(directory, 'right', CASES[1])
            packet = json.loads(right.read_text())
            packet['scene']['crossing_zone_rect_m'] = [-1, 0, 30, 30]
            right.write_text(json.dumps(packet), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fixed original geometry'):
                audit(left, right, 'children_presence')

    def test_queue_and_immutable_source_inventory(self):
        repo = Path(__file__).resolve().parents[3]
        source = audit_sources(repo)
        self.assertEqual(source['accepted_metadata_count'], 0)
        self.assertEqual(len(source['missing_source_classes']), 6)
        proposal = build()
        self.assertEqual(len(proposal['cases']), 6)
        self.assertEqual(len(proposal['comparison_audit_commands']), 5)
        self.assertEqual([x['order'] for x in proposal['cases']], list(range(1, 7)))
        for row in proposal['cases']:
            self.assertIn('--root "$LOCAL_ROOT" prepare-delivery', row['prepare_command'])
            self.assertIn('--root "$LOCAL_ROOT" execute-delivery', row['execute_command'])
            self.assertIn('--root "$LOCAL_ROOT" accept-delivery', row['accept_command'])
            self.assertIn('--review-archive /external/archive', row['accept_command'])


if __name__ == '__main__':
    unittest.main()
