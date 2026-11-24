"""Bind two source-preserving 600-frame engineering alternatives per parking case."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def current_cameras(bundle):
    for item in bundle['files']:
        if item['path'] == 'cameras.py':
            item['content'] = item['content'].replace('"name":"intersection"',
                '"name":"reference_corner"').replace('"name":"parking"',
                '"name":"driver_reference"')
        elif item['path'] == 'finalize.py':
            item['content'] = item['content'].replace("('overview','approach','intersection','parking')",
                "('overview','approach','reference_corner','driver_reference')")
        elif item['path'] == 'config.json':
            config = json.loads(item['content'])
            names = {'intersection': 'reference_corner', 'parking': 'driver_reference'}
            for camera in config['cameras']:
                camera['name'] = names.get(camera['name'], camera['name'])
            item['content'] = json.dumps(config, indent=2) + '\n'
    return bundle


def main():
    summary = []
    for suffix in ('probe_a', 'probe_b'):
        manifest = json.loads((HERE / f'current-v2-{suffix}-primary-manifest.json').read_text())
        case = manifest['cases'][0]
        source = json.loads((HERE / 'draft-execution-manifest-600.json').read_text())
        draft = next(x for x in source['cases'] if x['case_id'] == case['case_id'])
        candidates = []
        for candidate_id in ('fallback1', 'fallback2'):
            entry = next(x for x in draft['candidates'] if x['id'] == candidate_id)
            bundle = current_cameras(json.loads((HERE / entry['construction']).read_text()))
            path = HERE / f'current-v2-candidates/{suffix}/{candidate_id}/construction.json'
            write(path, bundle)
            candidates.append({**entry,
                'construction': path.relative_to(HERE).as_posix(),
                'construction_sha256': sha(path)})
        case['candidates'] = candidates
        output = HERE / f'current-v2-{suffix}-candidate-manifest.json'
        write(output, manifest)
        summary.append({'case_id': case['case_id'], 'manifest': output.name,
                        'sha256': sha(output), 'candidate_count': len(candidates)})
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
