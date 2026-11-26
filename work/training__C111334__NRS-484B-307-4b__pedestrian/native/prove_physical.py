"""Exercise complete, incomplete and missing pedestrian source outcomes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111334-physical'
SUFFIXES = ('probe_1', 'probe_2', 'permission_before_entry')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def lines(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def prove():
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if ROOT / '.runtime-work' not in output_root.parents:
        raise ValueError('Set output root under .runtime-work')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((PACKAGE / 'native-draft-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        construction = json.loads((PACKAGE / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        source = PACKAGE / 'native/diagnostic' / suffix / 'sources'
        original = [json.loads(s) for s in
                    (source / 'c111334-native-samples.jsonl').read_text().splitlines()]
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            attempt = SCRATCH / suffix / kind
            attempt.mkdir(parents=True, exist_ok=True)
            save(attempt / 'config.json', config)
            (attempt / 'video_frames.jsonl').write_text(
                (source / 'video_frames.jsonl').read_text())
            samples = json.loads(json.dumps(original))
            if kind == 'incomplete_motion':
                target_y = 0 if suffix == 'probe_1' else 5
                for row in samples:
                    row['pedestrian_body_polygon_xy_m'] = [
                        [point[0], target_y + (-0.2 if i < 2 else 0.2)]
                        for i, point in enumerate(row['pedestrian_body_polygon_xy_m'])]
            if kind != 'missing_evidence':
                lines(attempt / 'c111334-native-samples.jsonl', samples)
            result = PACKAGE / ('physical-' + suffix + '-' + kind + '.json')
            log = PACKAGE / ('physical-' + suffix + '-' + kind + '.log')
            command = [sys.executable, '-B', str(HERE / 'physical_outcome.py'),
                       '--attempt', str(attempt), '--case', entry['case_id'],
                       '--output', str(result)]
            completed = subprocess.run(command, cwd=ROOT, text=True,
                                       capture_output=True, timeout=60)
            log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
            if completed.returncode != 0:
                raise RuntimeError('Physical fixture failed: ' + suffix + ' ' + kind)
            outcome = json.loads(result.read_text())
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if outcome['physical_checks']['maneuver']['status'] != expected:
                raise AssertionError('Physical fixture status differed: ' + suffix + ' ' + kind)
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': 0, 'log': log.name,
                             'log_sha256': sha(log), 'result': result.name,
                             'result_sha256': sha(result)})
        lifecycle_log = PACKAGE / ('physical-' + suffix + '-lifecycle.log')
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        lifecycle_log.write_text('Synthetic lifecycle order: ' + ' '.join(events) + '\n')
        receipt = {
            'format': 'c111334-physical-preparation-cpu-v1',
            'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'fixtures': fixtures,
            'lifecycle': {'events': events, 'exit_code': 0,
                          'log': lifecycle_log.name,
                          'log_sha256': sha(lifecycle_log)},
            'original_native_observed': False,
            'legal_verdict_claimed': False,
        }
        target = PACKAGE / ('physical-' + suffix + '-preparation.json')
        save(target, receipt)
    return {'cases': len(SUFFIXES), 'fixture_count': len(SUFFIXES) * 3}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
