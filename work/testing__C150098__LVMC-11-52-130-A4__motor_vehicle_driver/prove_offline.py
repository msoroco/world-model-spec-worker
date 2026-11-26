"""Run the pinned runtime's exact offline bundle checks for eleven cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from hydrant import ASSIGNMENT, CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c150098' / 'offline'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')


def proof():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / 'execution-manifest.json'
    entries = []
    for case in CASES:
        name = case.suffix
        construction = HERE / ('construction-' + name + '.json')
        entries.append({'case_id': ASSIGNMENT + '__' + name, 'kind': 'delivery',
                        'construction': construction.name,
                        'construction_sha256': sha(construction),
                        'fixture_recipe': 'work/' + ASSIGNMENT + '/diagnostics/' + name + '-recipe.json',
                        'measurement_contract': 'diagnostics/' + name + '-measurement-contract.json',
                        'measurement_procedure': {'entrypoint': 'analysis.py'},
                        'source_gate': 'reviewed original municipal parallel-parking authority, physical hydrant and Native map required',
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'acquisition': {channel: {'entrypoint': 'native_runner.py',
                            'method': 'capture_original',
                            'evidence': 'Post-tick original hydrant/body, reviewed authority and four camera frame IDs.'}
                            for channel in ('longitudinal_hydrant_gap',
                                            'parallel_parking_authority', 'vehicle_activity',
                                            'exception_source', 'camera_frame_identity')},
                        'candidate_risk': {'status': 'physical',
                            'reason': 'Hydrant placement and camera visibility require measured local fallback assessment.'},
                        'candidates': []})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'status': 'source_gated_draft',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries, 'comparisons': []}
    write(manifest_path, manifest)
    environment = dict(os.environ)
    environment['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work' / 'c150098' / 'output-root')
    environment['TMPDIR'] = str(ROOT / '.runtime-work' / 'c150098' / 'tmp')
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    Path(environment['SCENARIO_PIPELINE_OUTPUT_ROOT']).mkdir(parents=True, exist_ok=True)
    Path(environment['TMPDIR']).mkdir(parents=True, exist_ok=True)
    for entry in entries:
        name = entry['case_id'].removeprefix(ASSIGNMENT + '__')
        destination = SCRATCH / name
        if destination.exists():
            shutil.rmtree(destination)
        command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                   '--manifest', str(manifest_path), '--case', entry['case_id'],
                   '--output', str(destination), '--python', sys.executable]
        process = subprocess.run(command, cwd=ROOT, env=environment,
                                 capture_output=True, text=True, timeout=300)
        log_path = HERE / ('cpu-offline-' + name + '.log')
        details = (destination / 'offline.log').read_text(encoding='utf-8') if (destination / 'offline.log').exists() else ''
        log_path.write_text((details + process.stdout + process.stderr).rstrip() + '\n', encoding='utf-8')
        if process.returncode:
            raise RuntimeError('exact offline failed: ' + name + ' (see ' + str(log_path) + ')')
        entry['offline'] = {'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' +
                            ASSIGNMENT + '/execution-manifest.json --case ' + entry['case_id'] +
                            ' --output $OUTPUT --python $CPU_PYTHON',
                            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
                            'log': log_path.name, 'log_sha256': sha(log_path)}
        write(manifest_path, manifest)
        print('offline passed:', name)
    return manifest


if __name__ == '__main__':
    proof()
