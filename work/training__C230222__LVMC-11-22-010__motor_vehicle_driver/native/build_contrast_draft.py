"""Build a second unselected capture probe from the reviewed reference source.

The control schedule changes a motion cue. It makes no attention inference.
"""
import hashlib
import json
from pathlib import Path

from build_draft_bundle import ROOT, NATIVE, TESTS, write


CASE = ROOT.name + '__contrast'


def main():
    reference = json.loads(
        (ROOT / 'draft-primary/reference/primary/construction.json').read_text())
    config = json.loads((NATIVE / 'config.json').read_text())
    config['case_id'] = CASE
    config['selected_case_id'] = CASE
    config['control_phases'][1]['throttle'] = 0.10
    config['control_phases'][2]['throttle'] = 0.08
    construction = dict(reference)
    construction['case_id'] = CASE
    construction['measurement_plan'] = (
        'Retain 600 original Native ego frames, joined four-camera sources, '
        'and the deliberate control-request difference. Independent original '
        'operator review is still required for attention.')
    construction['status'] = 'draft_cpu_offline_only'
    construction['files'] = [dict(item) for item in reference['files']]
    for item in construction['files']:
        if item['path'] == 'config.json':
            item['content'] = json.dumps(config, indent=2) + '\n'
        if item['path'] == 'tests/test_offline.py':
            item['content'] = TESTS + '''\n\nclass ContrastControl(unittest.TestCase):\n    def test_control_request_only(self):\n        config = json.loads(Path('config.json').read_text())\n        self.assertEqual([phase['throttle'] for phase in config['control_phases']],\n                         [0.24, 0.10, 0.08])\n        self.assertIsNone(config['driver_attention_to_operation'])\n        self.assertIsNone(config['legal_verdict'])\n'''
    source = ROOT / 'draft-primary/contrast/primary/construction.json'
    write(source, construction)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        'assignment_id': ROOT.name,
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'status': 'draft_cpu_offline_only',
        'cases': [{
            'case_id': CASE, 'kind': 'draft_not_selected',
            'construction': str(source.relative_to(ROOT)),
            'construction_sha256': digest,
            'candidate_risk': {'status': 'physical',
                               'reason': 'The motion cue and operator visibility '
                                         'require original Native evidence.'},
        }],
    }
    write(ROOT / 'draft-contrast-manifest.json', manifest)
    print(json.dumps({'case_id': CASE, 'construction_sha256': digest}))


if __name__ == '__main__':
    main()
