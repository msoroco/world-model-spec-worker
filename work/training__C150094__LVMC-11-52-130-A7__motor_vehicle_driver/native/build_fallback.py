"""Build one shared braking alternative for the linked driveway cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for row in manifest['cases']:
        case = row['case_id']
        probe = case[-2:]
        primary = json.loads((ROOT / row['construction']).read_text())
        files = []
        for item in primary['files']:
            changed = dict(item)
            if item['path'] == 'runner.py':
                runner = item['content']
                runner = runner.replace("config.get('candidate_id') != 'primary'",
                                        "config.get('candidate_id') != 'fallback1'")
                runner = runner.replace('max(3.0, speed**2/4.0)',
                                        'max(4.0, speed**2/3.0)')
                runner = runner.replace('else .27', 'else .18')
                if runner == item['content']:
                    raise ValueError('Fallback did not change controller')
                changed['content'] = runner
            if item['path'] == 'config.json':
                config = json.loads(item['content'])
                config['candidate_id'] = 'fallback1'
                changed['content'] = json.dumps(config, indent=2) + '\n'
            files.append(changed)
        fallback = dict(primary)
        fallback['files'] = files
        source = HERE / f'fallback1-probe_{probe}-construction.json'
        source.write_text(json.dumps(fallback, indent=2, sort_keys=True) + '\n')
        candidate = {
            'id': 'fallback1',
            'construction': str(source.relative_to(ROOT)),
            'construction_sha256': sha(source),
            'changed_knobs': ['brake lookahead floor: 3.0 -> 4.0 m',
                              'speed braking denominator: 4.0 -> 3.0',
                              'approach throttle: 0.27 -> 0.18'],
            'trigger': {
                'source': 'native_parking_trace.jsonl',
                'metric': 'stationary body-footprint gap against surveyed driveway curb interval',
                'failure_condition': 'primary stationary measured gap differs from the case target by more than 0.25 m'},
            'offline': {}, 'compatibility': {},
        }
        row['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Live braking can overshoot the surveyed stop centre and miss the exact measured gap'}
        row['candidates'] = [candidate]
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
