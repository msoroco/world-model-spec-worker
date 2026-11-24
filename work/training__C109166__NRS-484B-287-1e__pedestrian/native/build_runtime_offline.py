"""Package exact unselected diagonal source cases for current-runtime offline tests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
SOURCE = ROOT / 'inputs' / ASSIGNMENT.name / 'assignment.json'
LAW_SHA = 'b9932c768eab337188ef1388f1d0f09f8e3ee7b876882ef3c2423c38c2d6bd04'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CHECK = '''"""Exact copied diagonal source integrity; no physical claim."""
import json
from pathlib import Path
from diagonal import measure, sha, synthetic_rows

HERE = Path.cwd()

def check():
    config = json.loads((HERE / 'config.json').read_text())
    source = json.loads((HERE / 'assignment-source.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if (config['assignment_sha256'] != sha(HERE / 'assignment-source.json') or
            config['plan_sha256'] != sha(HERE / 'case-plan.json') or
            config['source_sha256'] != sha(HERE / 'diagonal-source.jsonl') or
            config['context_sha256'] != sha(HERE / 'diagonal-context.json') or
            source['law']['text'] != plan['source_law']['text'] or
            plan['source_law']['sha256'] != config['law_sha256'] or
            source['actor'] != 'pedestrian' or source['cell']['cell_id'] != 'C109166'):
        raise ValueError('Copied diagonal source, plan or law changed')
    rows = [json.loads(line) for line in (HERE / 'diagonal-source.jsonl').read_text().splitlines()]
    if rows != synthetic_rows(config['case_suffix']):
        raise ValueError('Diagonal source is not the exact controlled request')
    result = measure(HERE / 'diagonal-source.jsonl', HERE / 'diagonal-context.json')
    if result['first_entry_device_state'] != config['first_entry_state']:
        raise ValueError('First-entry device state differs')
    if result['physical_crossing_observed'] or result['legal_verdict_claimed']:
        raise ValueError('Synthetic request claimed physical/legal status')
    return result

if __name__ == '__main__':
    print(json.dumps(check()))
'''

TEST = '''import unittest
from check import check

class ExactDiagonalRequest(unittest.TestCase):
    def test_exact_source_and_first_entry(self):
        row = check()
        self.assertEqual(row['frames'], 600)
        self.assertFalse(row['physical_crossing_observed'])
        self.assertFalse(row['legal_verdict_claimed'])
'''


def build():
    plan = ASSIGNMENT / 'case-plan.json'
    law = json.loads(plan.read_text())['source_law']
    if law['sha256'] != LAW_SHA or json.loads(SOURCE.read_text())['law']['text'] != law['text']:
        raise ValueError('Frozen diagonal law source changed')
    entries = []
    for suffix, expected in (('controlled_1', 'diagonal_walk'),
                             ('controlled_2', 'diagonal_dont_walk')):
        folder = ASSIGNMENT / 'diagnostic-diagonal'
        source = folder / (suffix + '.jsonl')
        context = folder / 'context.json'
        config = {'case_id': ASSIGNMENT.name + '__' + suffix,
                  'case_suffix': suffix, 'candidate_id': 'primary',
                  'assignment_sha256': sha(SOURCE), 'plan_sha256': sha(plan),
                  'source_sha256': sha(source), 'context_sha256': sha(context),
                  'law_sha256': LAW_SHA, 'first_entry_state': expected,
                  'frames': 600, 'rate_hz': 20, 'duration_s': 30,
                  'selected': False, 'original_native_observed': False}
        files = [{'path': name, 'content': content} for name, content in (
            ('assignment-source.json', SOURCE.read_text()),
            ('case-plan.json', plan.read_text()),
            ('diagonal-source.jsonl', source.read_text()),
            ('diagonal-context.json', context.read_text()),
            ('diagonal.py', (HERE / 'diagonal.py').read_text()),
            ('check.py', CHECK), ('tests/test_exact.py', TEST),
            ('config.json', json.dumps(config, indent=2) + '\n'))]
        construction = {'case_id': config['case_id'], 'cell_id': 'C109166',
                        'law_id': 'NRS-484B-287-1e', 'actor': 'pedestrian',
                        'entrypoint': 'check.py', 'files': files,
                        'status': 'unselected_cpu_diagnostic',
                        'recording_description': 'Authored diagonal first-entry device-state request; no original official-device review.'}
        target = HERE / 'runtime-drafts' / suffix / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': config['case_id'],
                        'construction': str(target.relative_to(HERE)),
                        'construction_sha256': sha(target), 'candidates': [],
                        'candidate_risk': {'status': 'physical',
                            'reason': 'Official device authority, Native crossing and exception remain unverified.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT.name, 'status': 'draft_not_selected',
                'cases': entries, 'original_native_observed': False,
                'delivery_ready': False}
    path = HERE / 'draft-execution-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    build()
