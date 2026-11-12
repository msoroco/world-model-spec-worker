"""Replay a reflected 1,100-frame left approach through saved finalization."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO / '.runtime-work/c125714-250-2-saved-full-duration-v1/positive'
OUTPUT = REPO / '.runtime-work/c125714-left-full-duration-v1'
CASE = ROOT.name + '__source_verified_other_left_near_time'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit
from worker_exchange.measurement_contract import validate, verify_report
from worker_exchange.runtime_cli import execution_env


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    attempt = OUTPUT / 'positive'
    attempt.mkdir(parents=True)
    (attempt / 'capture').mkdir()
    fixed = ('video_frames.jsonl', 'trace.jsonl', 'controller_history.jsonl',
             'capture/evidence.jsonl', 'overview.mkv', 'approach.mkv',
             'reference_corner.mkv', 'driver_reference.mkv')
    source_hashes = {name: sha(SOURCE / name) for name in fixed}
    for name in fixed:
        target = attempt / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, target)
    geometry = json.loads((SOURCE / 'road_geometry.json').read_text())
    geometry['other_approach_heading_deg'] = -90
    geometry['other_approach_origin_xy_m'] = [0, 8]
    (attempt / 'road_geometry.json').write_text(json.dumps(geometry) + '\n')
    config = json.loads((SOURCE / 'config.json').read_text())
    config['selected_case_id'] = CASE
    (attempt / 'config.json').write_text(json.dumps(config) + '\n')
    with (attempt / 'crossing_history.jsonl').open('x') as output:
        for line in (SOURCE / 'crossing_history.jsonl').read_text().splitlines():
            row = json.loads(line)
            other = row['other']
            other['position_xy_m'][1] *= -1
            other['body_vertices_xy_m'] = [[x, -y] for x, y in other['body_vertices_xy_m']]
            output.write(json.dumps(row, allow_nan=False) + '\n')
    command = [sys.executable, str(ROOT / 'finalizer.py'), '--attempt', str(attempt),
               '--output', str(attempt / 'analysis-report.json')]
    subprocess.run(command, check=True, timeout=120, env=execution_env(),
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    report = json.loads((attempt / 'analysis-report.json').read_text())
    contract = json.loads((ROOT / 'cases/source_verified_other_left_near_time/measurement-contract.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    validate(contract, plan['requirement_dispositions'], (ROOT / 'finalizer.py').read_text(), CASE)
    measurements = verify_report(contract, report, attempt)
    observed = report['measurement']
    if observed['other_is_to_ego_right'] is not False or observed['ego_minus_other_entry_time_s'] != 1.5:
        raise ValueError('Full-duration left approach or measured entry order differs')
    mapping = sha(attempt / 'video_frames.jsonl')
    cameras = {}
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        receipt = audit(attempt / (name + '.mkv'), 1100, mapping_sha256=mapping)
        cameras[name] = {'frames': receipt['frames'], 'source_sha256': receipt['video_sha256']}
    negative = OUTPUT / 'missing-crossing'
    negative.mkdir()
    (negative / 'capture').mkdir()
    for name in ('config.json', 'road_geometry.json', *fixed):
        target = negative / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(attempt / name, target)
    failed = subprocess.run([sys.executable, str(ROOT / 'finalizer.py'), '--attempt', str(negative),
                             '--output', str(negative / 'analysis-report.json')],
                            env=execution_env(), capture_output=True, text=True, timeout=120)
    if failed.returncode == 0 or contract['negative']['error_contains'] not in failed.stdout + failed.stderr:
        raise ValueError('Missing original crossing history was accepted')
    if any(sha(SOURCE / name) != checksum for name, checksum in source_hashes.items()):
        raise ValueError('Original right-side sources changed during reflection')
    result = {'format': 'worker-c125714-left-full-duration-diagnostic', 'case_id': CASE,
              'frames': 1100, 'rate_hz': 20, 'other_is_to_ego_right': False,
              'entry_delta_s': observed['ego_minus_other_entry_time_s'],
              'measurements': sorted(measurements), 'camera_decodes': cameras,
              'negative_removed': 'crossing_history.jsonl',
              'source_hashes_preserved': True, 'physical_acceptance_claimed': False,
              'legal_judgment': 'unresolved'}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
