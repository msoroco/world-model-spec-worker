"""Exercise three source-bound physical outcomes per school-zone case."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / '.runtime-work' / 'c262666-test' / 'physical'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work' / 'c262666-test' / 'output'),
               TMPDIR=str(REPO / '.runtime-work' / 'c262666-test'), PYTHONDONTWRITEBYTECODE='1')
    lifecycle = FOLDER / 'physical-lifecycle.log'
    lifecycle.write_text('Synthetic CPU lifecycle order: capture_finished, encoders_closed, restoration_verified, native_exit, owner_released, saved_processing_started. Original Native release is pending.\n')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        source = REPO / '.runtime-work' / 'c262666-test' / ('compat-r5' if suffix == 'probe_03' else f'compat-{suffix}-r1')
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            attempt = SCRATCH / suffix / kind
            attempt.mkdir(parents=True, exist_ok=True)
            for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl', 'result.json'):
                shutil.copyfile(source / name, attempt / name)
            if kind == 'incomplete_motion':
                rows = [json.loads(s) for s in (attempt / 'trace.jsonl').read_text().splitlines()]
                first = rows[0]['position_m']
                for row in rows:
                    row['position_m'] = first
                    row['position'] = dict(zip(('x', 'y', 'z'), first))
                (attempt / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            if kind == 'missing_evidence':
                (attempt / 'trace.jsonl').unlink()
            result_name = f'physical-{suffix}-{kind}.json'
            log_name = f'physical-{suffix}-{kind}.log'
            command = [sys.executable, str(FOLDER / 'physical_outcome.py'), '--attempt', str(attempt),
                       '--case', entry['case_id'], '--output', str(FOLDER / result_name)]
            run = subprocess.run(command, env=env, text=True, capture_output=True)
            (FOLDER / log_name).write_text((run.stdout + run.stderr).rstrip() + '\n')
            if run.returncode:
                raise ValueError(f'Physical {suffix} {kind} failed: {(run.stdout + run.stderr)[-500:]}')
            result = json.loads((FOLDER / result_name).read_text())
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log_name, 'log_sha256': sha(FOLDER / log_name),
                             'result': result_name, 'result_sha256': sha(FOLDER / result_name),
                             'observed': result['physical_checks']['maneuver']['status']})
        receipt = {'format': 'c262666-school-zone-physical-preparation-cpu-v1', 'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'], 'fixtures': fixtures,
                   'lifecycle': {'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                                            'native_exit', 'owner_released', 'saved_processing_started'],
                                 'exit_code': 0, 'log': lifecycle.name, 'log_sha256': sha(lifecycle)},
                   'original_native_observed': False, 'legal_verdict': None}
        path = FOLDER / f'physical-{suffix}-preparation.json'
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': path.name, 'sha256': sha(path)}
        print(suffix, [f['observed'] for f in fixtures], flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
