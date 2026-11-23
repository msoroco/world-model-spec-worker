"""Materialize two unselected exact taxi requests for pinned offline tests."""
import json
from pathlib import Path

from request import CASES, HERE, CASE, sha

TEST = '''import unittest
from pathlib import Path
from check import check

class ExactTaxiRequest(unittest.TestCase):
    def test_source_and_first_intersection(self):
        value = check(Path.cwd())
        self.assertEqual(value['frames'], 600)
        self.assertEqual(value['duration_s'], 30)
        self.assertFalse(value['stand_designation_verified'])
        self.assertFalse(value['posted_notice_verified'])
        self.assertFalse(value['original_native_observed'])
        self.assertFalse(value['delivery_ready'])
'''


def build():
    cases = []
    for suffix in CASES:
        bundle = HERE / 'drafts' / suffix
        names = ('assignment-source.json', 'case-plan.json', 'config.json',
                 'requested-tracks.jsonl')
        files = [{'path': name, 'content': (bundle / name).read_text()} for name in names]
        for name in ('request.py', 'check.py'):
            files.append({'path': name, 'content': (HERE / name).read_text()})
        files.append({'path': 'tests/test_exact.py', 'content': TEST})
        construction = {'case_id': CASE.name + '__' + suffix,
                        'cell_id': 'C110875', 'law_id': 'LVMC-11-60-090',
                        'actor': 'taxi_driver', 'entrypoint': 'check.py',
                        'files': files, 'status': 'unselected_cpu_diagnostic',
                        'recording_description': 'Authored stand-to-first-intersection request; designation, sign, cab qualification and Native route unverified.'}
        target = HERE / 'runtime-drafts' / suffix / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        cases.append({'case_id': construction['case_id'],
                      'construction': str(target.relative_to(HERE)),
                      'construction_sha256': sha(target),
                      'candidates': [],
                      'candidate_risk': {'status': 'none', 'reason': 'No selected Native candidate yet'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': CASE.name, 'status': 'draft_not_selected',
                'cases': cases, 'original_native_observed': False,
                'delivery_ready': False}
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases'])}))
