"""Use a common forward spawn offset if original Native stopping falls short."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'draft-execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        fallback = json.loads((HERE / entry['construction']).read_text())
        runner = next(row for row in fallback['files'] if row['path'] == 'runner.py')
        assert runner['content'].count('x=-20,y=target_y') == 1
        runner['content'] = runner['content'].replace('x=-20,y=target_y', 'x=-18,y=target_y')
        config = next(row for row in fallback['files'] if row['path'] == 'config.json')
        value = json.loads(config['content'])
        value['candidate_id'] = 'fallback1'
        config['content'] = json.dumps(value, indent=2) + '\n'
        fallback['mechanisms'] = ['Same premises, designation review, footprint target, controller, cameras and capture; move initial spawn forward 2 m if original Native vehicle stops short.']
        suffix = entry['case_id'].split('__')[-1]
        path = HERE / 'draft-exact' / suffix / 'fallback1/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, indent=2) + '\n')
        entry['candidates'] = [{'id': 'fallback1', 'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'original Native native-vehicle.jsonl and result.json',
                'metric': 'stationary original body frames centered in the requested bay or aisle',
                'failure_condition': 'fewer than 450 of 600 original frames with speed zero and body centered in the requested region, after checking no source loss'},
            'changed_knobs': ['initial vehicle spawn x from -20 m to -18 m for both linked cases']}]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print({e['case_id']: e['candidates'][0]['construction_sha256'] for e in manifest['cases']})


if __name__ == '__main__':
    main()
