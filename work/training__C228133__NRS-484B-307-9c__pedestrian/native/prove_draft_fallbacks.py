"""Run exact pinned offline construction checks for both linked draft cases."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
OWNER = HERE.parent
ROOT = HERE.parents[2]
MANIFEST = OWNER / 'draft-primary-manifest.json'
PROOF = OWNER / 'draft-fallback-offline-proof.json'
FALLBACK_FIELDS = {'fallback1': 'spawn_clearance_m',
                   'fallback2': 'walker_speed_mps',
                   'fallback3': 'camera_distance_m'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config_for(construction):
    rows = json.loads(construction.read_text())['files']
    return json.loads(next(row['content'] for row in rows if row['path'] == 'config.json'))


def main():
    manifest = json.loads(MANIFEST.read_text())
    receipt = {'format': 'c228133-draft-fallback-offline-proof-v1',
               'manifest': str(MANIFEST.relative_to(ROOT)),
               'manifest_sha256': sha(MANIFEST),
               'selected_for_delivery': False,
               'original_native_observed': False,
               'cases': []}
    for case in manifest['cases']:
        source = OWNER / case['construction']
        primary = config_for(source)
        item = {'case_id': case['case_id'], 'candidates': []}
        for candidate_id in ('primary', *FALLBACK_FIELDS):
            binding = (case if candidate_id == 'primary' else next(
                row for row in case['candidates'] if row['id'] == candidate_id))
            construction = OWNER / binding['construction']
            assert sha(construction) == binding['construction_sha256']
            config = config_for(construction)
            assert config['case_id'] == case['case_id']
            assert config['candidate_id'] == candidate_id
            assert config['duration_s'] == 30 and config['rate_hz'] == 20
            assert len(config['cameras']) == 4
            varying = {key for key in set(primary) | set(config)
                       if primary.get(key) != config.get(key)}
            expected = set() if candidate_id == 'primary' else {
                'candidate_id', FALLBACK_FIELDS[candidate_id]}
            assert varying == expected, (candidate_id, varying)
            suffix = case['case_id'].rsplit('__', 1)[-1]
            run_id = f'c228133-fallback-{suffix}-{candidate_id}-20261123'
            output = ROOT / '.runtime-work' / run_id
            command = [str(ROOT / '.venv-cpu/bin/python'),
                       str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case['case_id'],
                       '--output', str(output)]
            if candidate_id != 'primary':
                command += ['--candidate', candidate_id]
            log = OWNER / f'draft-fallback-{suffix}-{candidate_id}.log'
            env = os.environ.copy()
            env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(
                ROOT / '.runtime-work' / 'c228133-fallback-runtime-output')
            result = subprocess.run(command, cwd=ROOT, env=env,
                                    capture_output=True, text=True)
            log.write_text(result.stdout + result.stderr)
            if result.returncode != 0:
                raise RuntimeError(f'{candidate_id} {suffix} offline failed: {log}')
            item['candidates'].append({
                'id': candidate_id,
                'construction': binding['construction'],
                'construction_sha256': sha(construction),
                'changed_config_keys': sorted(varying),
                'command': ' '.join(command),
                'exit_code': result.returncode,
                'log': log.name,
                'log_sha256': sha(log),
            })
        receipt['cases'].append(item)
    PROOF.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof': PROOF.name, 'proof_sha256': sha(PROOF),
                      'exact_offline_checks': sum(len(c['candidates']) for c in receipt['cases'])}))


if __name__ == '__main__':
    main()
