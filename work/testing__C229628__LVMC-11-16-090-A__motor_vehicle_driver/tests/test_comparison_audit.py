"""Exercise fixed-condition and changed-variable rejection with textual fixtures."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import audit
from contest_aid import CASES
from native_source import AID
from test_contest_aid import scene, rows


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.base = Path('.runtime-work') / ('c229628-comparison-test-' + uuid4().hex)
        self.base.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.base)

    def packet(self, case):
        folder = self.base / case.name
        folder.mkdir()
        data = rows(case)
        for i, row in enumerate(data):
            row['native_frame'] = i + 50
        packet = {'assignment_id': AID, 'case_id': AID + '__' + case.name,
                  'scene': scene(case), 'frames': data}
        target = folder / 'contest-packet.json'
        target.write_text(json.dumps(packet) + '\n')
        (folder / 'original-source-receipt.json').write_text(json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture', 'diagnostic_fixture': True,
            'case_id': packet['case_id'],
            'packet_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}) + '\n')
        return folder

    def test_three_controlled_pairs_and_changed_fixed_condition(self):
        base = self.packet(CASES[0])
        for comparison, case in [('cue', CASES[1]), ('episode', CASES[2]),
                                 ('highway', CASES[3])]:
            with self.subTest(comparison=comparison):
                alternate = self.packet(case)
                result = audit(comparison, base, alternate, diagnostic=True)
                self.assertEqual(result['deliberate_difference'],
                                 {'cue': 'cue', 'episode': 'candidate_contest',
                                  'highway': 'highway'}[comparison])
        changed = self.base / CASES[1].name / 'contest-packet.json'
        packet = json.loads(changed.read_text())
        packet['scene']['ego_person_id'] = 'different-person'
        changed.write_text(json.dumps(packet) + '\n')
        with self.assertRaisesRegex(ValueError, 'sealed original'):
            audit('cue', base, changed.parent, diagnostic=True)


if __name__ == '__main__':
    unittest.main()
