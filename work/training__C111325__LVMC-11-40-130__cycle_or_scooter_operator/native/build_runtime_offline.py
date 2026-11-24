"""Bind two unselected exact-speed requests to the current offline runtime."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
FROZEN = ROOT / 'inputs' / ASSIGNMENT.name / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CHECK = '''"""Verify exact copied speed request and frozen statutory identity."""
import json
from pathlib import Path
from speed import measure, requested, sha

HERE = Path.cwd()

def check():
    cfg = json.loads((HERE / 'config.json').read_text())
    source = json.loads((HERE / 'assignment-source.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if (cfg['assignment_sha256'] != sha(HERE / 'assignment-source.json') or
            cfg['plan_sha256'] != sha(HERE / 'case-plan.json') or
            cfg['speed_source_sha256'] != sha(HERE / 'speed-source.jsonl') or
            cfg['context_sha256'] != sha(HERE / 'speed-context.json') or
            source['law']['text'] != plan['source_law']['text'] or
            source['cell']['cell_id'] != 'C111325'):
        raise ValueError('Copied bicycle law or source identity changed')
    rows = [json.loads(line) for line in (HERE / 'speed-source.jsonl').read_text().splitlines()]
    if rows != requested(cfg['condition']):
        raise ValueError('Exact bicycle speed request changed')
    result = measure(HERE / 'speed-source.jsonl', HERE / 'speed-context.json')
    if result['condition'] != cfg['condition']:
        raise ValueError('Speed condition changed')
    return result

if __name__ == '__main__':
    print(json.dumps(check()))
'''
TEST = '''import unittest
from check import check

class ExactSpeedRequest(unittest.TestCase):
    def test_source_and_law(self):
        result = check()
        self.assertEqual(result['frames'], 600)
        self.assertEqual(result['rate_hz'], 20)
        self.assertFalse(result['original_native_observed'])
        self.assertFalse(result['prudence_verdict_claimed'])
'''


def main():
    plan = ASSIGNMENT / 'case-plan.json'
    original = json.loads(FROZEN.read_text())
    planned = json.loads(plan.read_text())
    if original['law']['text'] != planned['source_law']['text']:
        raise ValueError('Frozen bicycle law text changed')
    entries = []
    for index, condition in enumerate(('condition_a', 'condition_b')):
        source = ASSIGNMENT / 'diagnostic-speed' / (condition + '.jsonl')
        context = ASSIGNMENT / 'diagnostic-speed/context.json'
        matches = [case['case_id'] for case in planned['cases'] if case['condition_index'] == index]
        if len(matches) != 1:
            raise ValueError('Missing planned speed condition')
        config = {'case_id': matches[0], 'condition': condition,
                  'candidate_id': 'primary', 'assignment_sha256': sha(FROZEN),
                  'plan_sha256': sha(plan), 'speed_source_sha256': sha(source),
                  'context_sha256': sha(context), 'frames': 600, 'rate_hz': 20,
                  'duration_s': 30, 'selected': False,
                  'original_native_observed': False}
        files = [{'path': name, 'content': content} for name, content in (
            ('assignment-source.json', FROZEN.read_text()),
            ('case-plan.json', plan.read_text()),
            ('speed-source.jsonl', source.read_text()),
            ('speed-context.json', context.read_text()),
            ('speed.py', (HERE / 'speed.py').read_text()),
            ('check.py', CHECK), ('tests/test_exact.py', TEST),
            ('config.json', json.dumps(config, indent=2) + '\n'))]
        construction = {'case_id': matches[0], 'cell_id': 'C111325',
                        'law_id': 'LVMC-11-40-130',
                        'actor': 'cycle_or_scooter_operator',
                        'entrypoint': 'check.py', 'files': files,
                        'status': 'unselected_cpu_diagnostic',
                        'recording_description': 'Authored 30-second bicycle speed request at a stop-sign approach; physical conditions and prudence unverified.'}
        target = HERE / 'runtime-drafts' / condition / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': matches[0],
                        'construction': str(target.relative_to(HERE)),
                        'construction_sha256': sha(target),
                        'candidates': [],
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Bicycle blueprint, Native speed, source cameras and contemporaneous conditions unverified.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT.name, 'status': 'draft_not_selected',
                'cases': entries, 'original_native_observed': False,
                'delivery_ready': False}
    target = HERE / 'draft-execution-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()
