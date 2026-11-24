"""Author one paired Native controller fallback without changing the law comparison."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / 'v2-native-draft-manifest.json'
OUT = HERE / 'v2-fallback-draft'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(BASE.read_text())
    OUT.mkdir(exist_ok=True)
    for entry in manifest['cases']:
        witness = entry['case_id'].rsplit('__', 1)[-1]
        primary = json.loads((HERE / entry['construction']).read_text())
        fallback = json.loads(json.dumps(primary))
        runner = next(item for item in fallback['files'] if item['path'] == 'runner.py')
        old = 'ego.apply_control(control_to(carla, ego, lookahead, 6))'
        if runner['content'].count(old) != 1:
            raise ValueError('Primary controller source changed')
        runner['content'] = runner['content'].replace(old,
            'ego.apply_control(control_to(carla, ego, lookahead, 7.5))')
        path = OUT / (witness + '-fallback1-construction.json')
        path.write_text(json.dumps(fallback, indent=2) + '\n')
        entry['candidate_risk'] = {'status': 'physical',
            'reason': 'Primary 6 m/s steering controller may not reach the authored exit connector within 600 original Native frames.'}
        entry['candidates'] = [{'id': 'fallback1',
            'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'native-raw-actors.jsonl',
                'metric': 'ordered original road 10 -> 11 -> 12 history by frame 599',
                'failure_condition': 'No original road 12 sample after road 11 before capture termination'},
            'changed_knobs': ['ego steering controller requested speed 6.0 to 7.5 m/s']}]
    path = HERE / 'v2-fallback-draft-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(path),
        'fallback_construction_sha256': [entry['candidates'][0]['construction_sha256']
                                        for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
