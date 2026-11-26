"""Run pinned exact offline checks for nine truck-following cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from truck_following import CASES
from native_packet import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c149752/offline'


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
        entry = {'case_id': AID + '__' + name, 'kind': 'delivery',
            'construction': construction.name, 'construction_sha256': sha(construction),
            'fixture_recipe': 'work/' + AID + '/diagnostics/' + name + '-recipe.json',
            'measurement_contract': 'diagnostics/' + name + '-measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'source_gate': 'reviewed Native public highway, lane topology, full truck mesh widths and four camera poses required',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'acquisition': {channel: {'entrypoint': 'runner.py', 'method': 'capture_original',
                'evidence': 'Post-tick truck, lane, entrant and four joined camera frame IDs.'}
                for channel in ('sealed_native_original_frames', 'original_body_vertices',
                                'full_mesh_width', 'map_lane_availability',
                                'vehicle_inventory', 'controller_commands', 'video_four_views')},
            'candidate_risk': {'status': 'physical' if case.passing else 'none',
                'reason': 'Opposing-lane pass and return may fail on reviewed Native route' if case.passing
                          else 'No special motion risk identified beyond primary source gate'},
            'candidates': []}
        if case.passing:
            fallback = HERE / ('construction-' + name + '-fallback1.json')
            entry['candidates'] = [{'id': 'fallback1', 'construction': fallback.name,
                'construction_sha256': sha(fallback),
                'trigger': {'source': 'original whole-body and lane relation history',
                            'metric': 'observed opposing-lane pass and return geometry',
                            'failure_condition': 'whole-body pass or return is absent in original frames'},
                'changed_knobs': ['matched subject/lead speed 11 m/s instead of 13 m/s']}]
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'status': 'source_gated_draft',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries, 'comparisons': []}
    write(manifest_path, manifest)
    environment = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c149752/output-root'),
                       TMPDIR=str(ROOT / '.runtime-work/c149752/tmp'), PYTHONDONTWRITEBYTECODE='1')
    for entry in entries:
        name = entry['case_id'].removeprefix(AID + '__')
        for candidate in (['primary', 'fallback1'] if entry['candidates'] else ['primary']):
            suffix = name + ('' if candidate == 'primary' else '-fallback1')
            destination = SCRATCH / suffix
            if destination.exists():
                shutil.rmtree(destination)
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(manifest_path), '--case', entry['case_id'],
                       '--output', str(destination), '--python', sys.executable]
            if candidate != 'primary':
                command += ['--candidate', candidate]
            process = subprocess.run(command, cwd=ROOT, env=environment,
                                     capture_output=True, text=True, timeout=300)
            log_path = HERE / ('cpu-offline-' + suffix + '.log')
            details = (destination / 'offline.log').read_text(encoding='utf-8') if (destination / 'offline.log').exists() else ''
            log_path.write_text((details + process.stdout + process.stderr).rstrip() + '\n', encoding='utf-8')
            if process.returncode:
                raise RuntimeError('exact offline failed: ' + suffix + ' (see ' + str(log_path) + ')')
            proof_row = {'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + AID +
                         '/execution-manifest.json --case ' + entry['case_id'] +
                         (' --candidate fallback1' if candidate != 'primary' else '') +
                         ' --output $OUTPUT --python $CPU_PYTHON',
                         'exit_code': 0, 'construction_sha256': entry['construction_sha256']
                         if candidate == 'primary' else entry['candidates'][0]['construction_sha256'],
                         'log': log_path.name, 'log_sha256': sha(log_path)}
            if candidate == 'primary':
                entry['offline'] = proof_row
            else:
                entry['candidates'][0]['offline'] = proof_row
            print(suffix + ': offline passed', flush=True)
    write(manifest_path, manifest)


if __name__ == '__main__':
    proof()
