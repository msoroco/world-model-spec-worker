"""Build two unselected exact-source offline constructions for C109128."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
SOURCE = ROOT / 'inputs' / ASSIGNMENT.name / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

CHECK = '''"""Exact copied sidewalk bypass source and frozen law identity."""
import json
from pathlib import Path
from bypass import measure, requested, sha

HERE = Path.cwd()

def check():
    cfg = json.loads((HERE / 'config.json').read_text())
    source = json.loads((HERE / 'assignment-source.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if (cfg['assignment_sha256'] != sha(HERE / 'assignment-source.json') or
            cfg['plan_sha256'] != sha(HERE / 'case-plan.json') or
            cfg['bypass_source_sha256'] != sha(HERE / 'bypass-source.jsonl') or
            cfg['context_sha256'] != sha(HERE / 'bypass-context.json') or
            source['law']['text'] != plan['source_law']['text'] or
            source['actor'] != 'pedestrian' or source['cell']['cell_id'] != 'C109128'):
        raise ValueError('Copied bypass law/source identity changed')
    rows = [json.loads(line) for line in (HERE / 'bypass-source.jsonl').read_text().splitlines()]
    if rows != requested(cfg['condition']):
        raise ValueError('Exact bypass request changed')
    measured = measure(HERE / 'bypass-source.jsonl', HERE / 'bypass-context.json')
    if measured['requested_bypass_path'] != cfg['condition']:
        raise ValueError('Bypass condition changed')
    return measured

if __name__ == '__main__':
    print(json.dumps(check()))
'''
TEST = '''import unittest
from check import check

class ExactBypassRequest(unittest.TestCase):
    def test_exact_source(self):
        row = check()
        self.assertEqual(row['frames'], 600)
        self.assertEqual(row['rate_hz'], 20)
        self.assertFalse(row['physical_obstruction_verified'])
        self.assertFalse(row['legal_verdict_claimed'])
'''


def build():
    plan = ASSIGNMENT / 'case-plan.json'
    original = json.loads(SOURCE.read_text())
    planned = json.loads(plan.read_text())
    if original['law']['text'] != planned['source_law']['text']:
        raise ValueError('Frozen law text changed')
    entries = []
    for condition in ('condition_a', 'condition_b'):
        source = ASSIGNMENT / 'diagnostic-bypass' / (condition + '.jsonl')
        context = ASSIGNMENT / 'diagnostic-bypass/context.json'
        matching = [item['case_id'] for item in planned['cases'] if item['condition_index'] == (0 if condition == 'condition_a' else 1)]
        if len(matching) != 1:
            raise ValueError('Planned condition identity missing')
        config = {'case_id': matching[0], 'condition': condition,
                  'candidate_id': 'primary', 'assignment_sha256': sha(SOURCE),
                  'plan_sha256': sha(plan), 'bypass_source_sha256': sha(source),
                  'context_sha256': sha(context), 'frames': 600,
                  'rate_hz': 20, 'duration_s': 30,
                  'original_native_observed': False, 'selected': False}
        files = [{'path': name, 'content': content} for name, content in (
            ('assignment-source.json', SOURCE.read_text()),
            ('case-plan.json', plan.read_text()),
            ('bypass-source.jsonl', source.read_text()),
            ('bypass-context.json', context.read_text()),
            ('bypass.py', (HERE / 'bypass.py').read_text()),
            ('check.py', CHECK), ('tests/test_exact.py', TEST),
            ('config.json', json.dumps(config, indent=2) + '\n'))]
        construction = {'case_id': matching[0], 'cell_id': 'C109128',
                        'law_id': 'NRS-484B-297-6', 'actor': 'pedestrian',
                        'entrypoint': 'check.py', 'files': files,
                        'status': 'unselected_cpu_diagnostic',
                        'recording_description': 'Authored 30-second sidewalk obstruction bypass request; physical blockage and practicability unverified.'}
        target = HERE / 'runtime-drafts' / condition / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': matching[0],
                        'construction': str(target.relative_to(HERE)),
                        'construction_sha256': sha(target), 'candidates': [],
                        'candidate_risk': {'status': 'physical',
                          'reason': 'Sidewalk obstruction, road edge, due care and first practicable return unverified in Native.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT.name, 'status': 'draft_not_selected',
                'cases': entries, 'original_native_observed': False,
                'delivery_ready': False}
    target = HERE / 'draft-execution-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    build()
