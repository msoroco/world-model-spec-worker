"""Build one shared barrier-clearance alternative for the seven selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'
OLD = 'for y in (-4.0, 4.0):'
NEW = 'for y in (-5.0, 5.0):'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        primary = json.loads((HERE / entry['construction']).read_text())
        alternative = json.loads(json.dumps(primary))
        alternative['status'] = 'partial_native_fallback_physical_unverified'
        files = [item for item in alternative['files'] if item['path'] == 'runner.py']
        if len(files) != 1 or files[0]['content'].count(OLD) != 1:
            raise ValueError('Expected one unchanged primary barrier placement')
        files[0]['content'] = files[0]['content'].replace(OLD, NEW)
        configs = [item for item in alternative['files'] if item['path'] == 'config.json']
        if len(configs) != 1:
            raise ValueError('Expected one exact config')
        config = json.loads(configs[0]['content'])
        config['candidate_id'] = 'fallback1'
        configs[0]['content'] = json.dumps(config, indent=2) + '\n'
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        path = HERE / 'draft-exact' / suffix / 'fallback1' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(alternative, indent=2) + '\n')
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Native barrier footprint may leave insufficient clearance for the observed subject width',
        }
        entry['candidates'] = [{
            'id': 'fallback1',
            'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {
                'source': 'original Native trail-inventory.json and vehicle-poses.jsonl',
                'metric': 'barrier_clear_gap_m minus vehicle_width_m and observed collision-free passage',
                'failure_condition': 'primary opening lacks positive Native body clearance or the body fails to traverse the opening',
            },
            'changed_knobs': [
                'both barrier prop lateral centers move from -4/+4 m to -5/+5 m in all linked cases; route, source context and capture contract remain fixed',
            ],
        }]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'fallbacks': len(manifest['cases']), 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
