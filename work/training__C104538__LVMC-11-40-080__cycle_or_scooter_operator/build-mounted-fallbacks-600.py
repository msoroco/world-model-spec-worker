"""Prepare one shared approach-runway fallback for all linked rider cases."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    path = HERE / 'draft-thirty-second-execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        primary = json.loads((HERE / entry['construction']).read_text())
        candidate = copy.deepcopy(primary)
        candidate['candidate_id'] = 'fallback1'
        for part in candidate['files']:
            if part['path'] == 'config.json':
                config = json.loads(part['content'])
                config['candidate_id'] = 'fallback1'
                part['content'] = json.dumps(config, indent=2) + '\n'
        kind = {'controlled_1': 'mounted_obey', 'controlled_2': 'mounted_turn',
                'controlled_3': 'dismounted_turn'}[entry['case_id'].rsplit('__', 1)[-1]]
        relative = f'current-candidates/{kind}/fallback1/construction.json'
        target = HERE / relative
        write(target, candidate)
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Bicycle approach may not settle onto the signed lane before the governed turn region; original Native lane/body samples must decide.',
        }
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': relative,
            'construction_sha256': sha(target),
            'trigger': {'source': 'original Native lane and body samples joined to rider camera frames',
                        'metric': 'available_approach_runway_m',
                        'failure_condition': 'less than 35 m of measured settled approach before the sign'},
            'changed_knobs': ['approach start -35 m to -50 m'],
        }]
    write(path, manifest)
    print(json.dumps({'candidates': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
