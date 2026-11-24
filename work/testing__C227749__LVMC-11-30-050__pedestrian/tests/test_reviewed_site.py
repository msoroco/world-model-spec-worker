"""Source-integrity tests for the production Native crossing preflight."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_site import FACTS, audit_reviewed_site


class ReviewedSiteTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('.runtime-work').resolve()
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.attempt = Path(self.tmp.name)
        self.scene = json.loads((ROOT/'cases/outside_right_angle/scene.json').read_text())
        refs = {}
        for fact in FACTS:
            name = f'reviewed-source-documents/{fact}.txt'
            path = self.attempt/name
            path.parent.mkdir(exist_ok=True)
            path.write_text(f'Original reviewed {fact} source record\n')
            refs[fact] = {'path': name,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'finding': f'Independent {fact} review'}
        self.packet = {
            'provenance_kind': 'reviewed_original_site',
            'diagnostic_fixture': False,
            'case_id': self.scene['case_id'],
            'loaded_map_sha256': self.scene['map_source_sha256'],
            'starting_curb_xy_m': self.scene['starting_curb_xy_m'],
            'opposite_curb_xy_m': self.scene['opposite_curb_xy_m'],
            'crosswalk_boundaries_xy_m': self.scene['crosswalk_boundaries_xy_m'],
            'roadway_highway_public_use': 'reviewed_public_roadway',
            'governing_control': 'reviewed_none',
            'source_refs': refs,
        }
        self.write_packet()

    def write_packet(self):
        (self.attempt/'reviewed-site.json').write_text(json.dumps(self.packet)+'\n')

    def test_exact_original_source_bindings(self):
        result = audit_reviewed_site(self.scene, self.attempt)
        self.assertEqual(set(result['source_refs']), set(FACTS))
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_rejects_diagnostic_and_missing_fact(self):
        self.packet['diagnostic_fixture'] = True
        self.write_packet()
        with self.assertRaisesRegex(ValueError, 'diagnostic fixture'):
            audit_reviewed_site(self.scene, self.attempt)
        self.packet['diagnostic_fixture'] = False
        self.packet['source_refs'].pop('governing_control')
        self.write_packet()
        with self.assertRaisesRegex(ValueError, 'every site fact'):
            audit_reviewed_site(self.scene, self.attempt)

    def test_rejects_changed_source_and_scene(self):
        path = self.attempt/self.packet['source_refs']['starting_curb_xy_m']['path']
        path.write_text('Changed original source\n')
        with self.assertRaisesRegex(ValueError, 'hash/contents invalid'):
            audit_reviewed_site(self.scene, self.attempt)
        self.packet['source_refs']['starting_curb_xy_m']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.packet['opposite_curb_xy_m'] = [[0, 0], [0, 1]]
        self.write_packet()
        with self.assertRaisesRegex(ValueError, 'opposite curb differs'):
            audit_reviewed_site(self.scene, self.attempt)

    def test_rejects_source_escape(self):
        self.packet['source_refs']['roadway_highway_public_use']['path'] = '../outside.txt'
        self.write_packet()
        with self.assertRaisesRegex(ValueError, 'outside attempt'):
            audit_reviewed_site(self.scene, self.attempt)


if __name__ == '__main__':
    unittest.main()
