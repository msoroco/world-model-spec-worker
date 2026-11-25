"""Package the exact unselected 1d diagonal requests for pinned offline tests."""
import hashlib
import json
from pathlib import Path
from diagonal_motion import camera_plan

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
SOURCE = ROOT / 'inputs' / ASSIGNMENT.name / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CHECK = '''"""Exact copied source and law identity for an unselected diagonal request."""
import json
from pathlib import Path
from authorization import measure, requested, sha
from diagonal_motion import camera_plan, command
from native_request import validate_pair
from runner import check as check_runner

HERE = Path.cwd()

def check():
    cfg = json.loads((HERE / 'config.json').read_text())
    source = json.loads((HERE / 'assignment-source.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if (cfg['assignment_sha256'] != sha(HERE / 'assignment-source.json') or
            cfg['plan_sha256'] != sha(HERE / 'case-plan.json') or
            cfg['diagonal_source_sha256'] != sha(HERE / 'diagonal-source.jsonl') or
            cfg['context_sha256'] != sha(HERE / 'diagonal-context.json') or
            source['law']['text'] != plan['source_law_text'] or
            source['actor'] != 'pedestrian' or source['cell']['cell_id'] != 'C109166'):
        raise ValueError('Copied diagonal law/source identity changed')
    actual = [json.loads(line) for line in (HERE / 'diagonal-source.jsonl').read_text().splitlines()]
    if actual != requested(cfg['case_suffix']):
        raise ValueError('Diagonal authorization request changed')
    for index, row in enumerate(actual):
        if tuple(row['pedestrian_xy_m']) != command(index)['target_xy_m']:
            raise ValueError('Diagonal controller/source route changed')
    if [item['name'] for item in camera_plan()] != ['overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('Four camera acquisition plan changed')
    if validate_pair()['changed_device_frame_count'] != 600:
        raise ValueError('Whole-crossing device contrast changed')
    if check_runner(cfg)['native_executed']:
        raise ValueError('Offline runner asserted Native execution')
    measured = measure(HERE / 'diagonal-source.jsonl', HERE / 'diagonal-context.json')
    if measured['requested_authorization_at_entry'] != cfg['requested_authorization']:
        raise ValueError('First-entry authorization request changed')
    return measured

if __name__ == '__main__':
    print(json.dumps(check()))
'''

TEST = '''import unittest
from check import check

class ExactAuthorizationRequest(unittest.TestCase):
    def test_exact_source(self):
        row = check()
        self.assertEqual(row['frames'], 600)
        self.assertFalse(row['official_device_verified'])
        self.assertFalse(row['physical_crossing_observed'])
        self.assertFalse(row['legal_verdict_claimed'])
'''


def build():
    plan = ASSIGNMENT / 'case-plan.json'
    if json.loads(SOURCE.read_text())['law']['text'] != json.loads(plan.read_text())['source_law_text']:
        raise ValueError('Frozen exact law changed')
    entries = []
    for suffix, authorization in (('probe_01', True), ('probe_02', False)):
        folder = ASSIGNMENT / 'diagnostic-authorization'
        source = folder / (suffix + '.jsonl')
        context = folder / 'context.json'
        config = {'case_id': ASSIGNMENT.name + '__' + suffix,
                  'case_suffix': suffix, 'candidate_id': 'primary',
                  'requested_authorization': authorization,
                  'assignment_sha256': sha(SOURCE), 'plan_sha256': sha(plan),
                  'diagonal_source_sha256': sha(source),
                  'context_sha256': sha(context), 'frames': 600,
                  'rate_hz': 20, 'duration_s': 30,
                  'cell_id': 'C109166', 'law_id': 'NRS-484B-287-1d',
                  'actor': 'pedestrian',
                  'cameras': [{'name': item['name'], 'width': item['width'],
                               'height': item['height']} for item in camera_plan()],
                  'opendrive_signal_id': 'candidate-unverified-203',
                  'entry_proxy_x_m': -5.5,
                  'driver_reference_height_m': 3.0,
                  'original_native_observed': False, 'selected': False}
        files = [{'path': name, 'content': content} for name, content in (
            ('assignment-source.json', SOURCE.read_text()),
            ('case-plan.json', plan.read_text()),
            ('diagonal-source.jsonl', source.read_text()),
            ('diagonal-context.json', context.read_text()),
            ('authorization.py', (HERE / 'authorization.py').read_text()),
            ('diagonal_motion.py', (HERE / 'diagonal_motion.py').read_text()),
            ('camera_capture.py', (HERE / 'camera_capture.py').read_text()),
            ('native_request.py', (HERE / 'native_request.py').read_text()),
            ('runner.py', (ASSIGNMENT / 'runner.py').read_text()),
            ('check.py', CHECK), ('tests/test_exact.py', TEST),
            ('config.json', json.dumps(config, indent=2) + '\n'))]
        construction = {'case_id': config['case_id'], 'cell_id': 'C109166',
                        'law_id': 'NRS-484B-287-1d', 'actor': 'pedestrian',
                        'entrypoint': 'check.py', 'files': files,
                        'status': 'unselected_cpu_diagnostic',
                        'recording_description': 'Authored 30-second diagonal authorization request; original official device unverified.'}
        target = HERE / 'runtime-drafts' / suffix / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': config['case_id'],
                        'construction': str(target.relative_to(HERE)),
                        'construction_sha256': sha(target), 'candidates': [],
                        'candidate_risk': {'status': 'physical',
                            'reason': 'Official device authorization and NRS 484B.290 exception unverified.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT.name, 'status': 'draft_not_selected',
                'cases': entries, 'original_native_observed': False,
                'delivery_ready': False}
    target = HERE / 'draft-execution-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    build()
