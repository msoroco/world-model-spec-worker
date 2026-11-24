"""Bind one source-triggered lateral fallback across all linked same-map cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'v2-common-intersection-manifest.json').read_text())
    for number, entry in enumerate(manifest['cases'], 1):
        primary = json.loads((HERE / entry['construction']).read_text())
        fallback = json.loads(json.dumps(primary))
        for file in fallback['files']:
            if file['path'] == 'runner.py':
                old = 'max(-0.2, min(0.2, x_error))'
                if file['content'].count(old) != 1:
                    raise ValueError('Primary lateral correction changed')
                file['content'] = file['content'].replace(old, 'max(-0.4, min(0.4, x_error))')
            elif file['path'] == 'config.json':
                config = json.loads(file['content'])
                config['candidate_id'] = 'fallback1'
                file['content'] = json.dumps(config, indent=2) + '\n'
        path = HERE / f'draft-exact/common_intersection/probe_{number}/fallback1/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, indent=2) + '\n')
        entry['candidates'] = [{'id': 'fallback1', 'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'original Native actor-poses.jsonl and requested_path',
                        'metric': 'lateral_error_at_roadway_entry_m',
                        'failure_condition': 'Primary original body path misses requested crosswalk relation at roadway entry due to lateral tracking error'},
            'changed_knobs': ['Walker lateral correction clamp 0.2 to 0.4; same policy in all three linked cases']}]
    manifest['status'] = 'partial_common_intersection_fallback_cpu'
    (HERE / 'v2-common-fallback1-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(HERE / 'v2-common-fallback1-manifest.json'),
                      'constructions': [case['candidates'][0]['construction_sha256'] for case in manifest['cases']]}))


if __name__ == '__main__':
    main()
