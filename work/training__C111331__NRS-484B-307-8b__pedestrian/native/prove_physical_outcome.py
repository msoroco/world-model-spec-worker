"""Exercise complete, incomplete and missing synthetic source outcomes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

folder = Path(__file__).resolve().parent.parent
repo = folder.parents[1]
scratch = repo / '.runtime-work/c111331-physical'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2) + '\n')


def rows(path, values):
    Path(path).write_text(''.join(json.dumps(row) + '\n' for row in values))


def main():
    if os.environ.get('PYTHONDONTWRITEBYTECODE') != '1':
        raise ValueError('Disable Python bytecode in the work tree')
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((folder / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        source = [json.loads(line) for line in (folder / ('diagnostic-source-' + condition + '.jsonl')).read_text().splitlines()]
        spec = json.loads((folder / ('diagnostic-' + condition + '.json')).read_text())
        map_text = spec['files']['video_frames.jsonl']
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            attempt = scratch / condition / kind
            attempt.mkdir(parents=True, exist_ok=True)
            write(attempt / 'config.json', config)
            (attempt / 'video_frames.jsonl').write_text(map_text)
            if kind != 'missing_evidence':
                sample = json.loads(json.dumps(source))
                if kind == 'incomplete_motion':
                    y = 0.0 if not config['requested_entry'] else 5.0
                    for row in sample:
                        row['footprint_xy_m'] = [[point[0], y] for point in row['footprint_xy_m']]
                rows(attempt / 'red-entry-original.jsonl', sample)
            else:
                (attempt / 'red-entry-original.jsonl').unlink(missing_ok=True)
            result = folder / ('physical-' + condition + '-' + kind + '.json')
            log = folder / ('physical-' + condition + '-' + kind + '.log')
            cmd = [sys.executable, str(folder / 'physical_outcome.py'), '--attempt', str(attempt),
                   '--case', entry['case_id'], '--output', str(result)]
            with log.open('w') as handle:
                completed = subprocess.run(cmd, cwd=repo, stdout=handle, stderr=subprocess.STDOUT, check=False)
            if completed.returncode:
                raise ValueError('Physical fixture failed: ' + kind)
            proof = json.loads(result.read_text())
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if proof['physical_checks']['maneuver']['status'] != expected:
                raise ValueError('Physical fixture did not assess ' + expected)
            fixtures.append({'kind': kind, 'command': ' '.join(cmd), 'exit_code': 0,
                             'log': log.name, 'log_sha256': sha(log),
                             'result': result.name, 'result_sha256': sha(result)})
        lifecycle_log = folder / 'physical-lifecycle.log'
        lifecycle_log.write_text('Synthetic ordering: capture_finished encoders_closed restoration_verified native_exit owner_released saved_processing_started\n')
        receipt = {'format': 'c111331-physical-preparation-cpu-v1',
                   'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                                            'native_exit', 'owner_released', 'saved_processing_started'],
                                 'exit_code': 0, 'log': lifecycle_log.name,
                                 'log_sha256': sha(lifecycle_log)},
                   'original_native_observed': False, 'legal_verdict_claimed': False}
        target = folder / ('physical-' + condition + '-preparation.json')
        write(target, receipt)
        print(json.dumps({'case': condition, 'receipt_sha256': sha(target)}))


if __name__ == '__main__':
    main()
