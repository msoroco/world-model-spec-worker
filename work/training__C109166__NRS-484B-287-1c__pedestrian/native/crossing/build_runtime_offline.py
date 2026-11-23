"""Package unselected requests for the current pinned offline runner."""
import json
from pathlib import Path

from request import CASES, CASE, HERE, sha

TEST = '''import unittest
from pathlib import Path
from check import check

class ExactCrossingRequest(unittest.TestCase):
    def test_source_and_timing(self):
        value = check(Path.cwd())
        self.assertEqual(value['frames'], 600)
        self.assertEqual(value['duration_s'], 30)
        self.assertGreater(value['roadway_entry_request_time_s'], 0)
        self.assertFalse(value['pedestrian_native_observed'])
        self.assertFalse(value['delivery_ready'])
'''


def build():
    cases = []
    for crossing in CASES:
        bundle = HERE / 'drafts' / crossing
        names = ('assignment-source.json', 'case-plan.json', 'config.json',
                 'requested-tracks.jsonl')
        files = [{'path': name, 'content': (bundle / name).read_text()} for name in names]
        for name in ('request.py', 'check.py'):
            files.append({'path': name, 'content': (HERE / name).read_text()})
        files.append({'path': 'tests/test_exact.py', 'content': TEST})
        construction = {'case_id': CASE.name + '__' + crossing,
                        'cell_id': 'C109166', 'law_id': 'NRS-484B-287-1c',
                        'actor': 'pedestrian', 'entrypoint': 'check.py',
                        'files': files, 'status': 'unselected_cpu_diagnostic',
                        'recording_description': 'Authored crossing requests; official control, map adjacency, marking, Native trajectory and exception unverified.'}
        target = HERE / 'runtime-drafts' / crossing / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        cases.append({'case_id': construction['case_id'],
                      'construction': str(target.relative_to(HERE)),
                      'construction_sha256': sha(target), 'candidates': [],
                      'candidate_risk': {'status': 'none', 'reason': 'No selected Native candidate yet'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': CASE.name, 'status': 'draft_not_selected',
                'cases': cases, 'pedestrian_native_observed': False,
                'delivery_ready': False}
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases'])}))
