"""Exercise physical-motion states and Native owner ordering on synthetic inputs."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c153046-nov25d/physical'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def fixture(case: dict, kind: str, location: Path) -> tuple[Path, Path]:
    location.mkdir(parents=True, exist_ok=False)
    direction = case['draft_variables']['receiving_direction']
    route = 'two_way_routes' if direction == 'two_way' else 'one_way_routes'
    sources = {}
    for name in ('opendrive', 'official_signal', route, 'stop_reference'):
        path = location / (name + '.txt')
        path.write_text('synthetic ' + name + ' for ' + case['case_id'] + '\n')
        sources[name] = {'path': path.name, 'sha256': sha(path),
                         'citation': 'synthetic diagnostic', 'reviewer': 'fixture'}
    packet = {'format': 'c153046-red-left-site-v1', 'reviewer': 'fixture',
              'sources': sources, 'approach_one_way': True,
              'receiving_one_way_to_left': direction == 'one_way_left',
              'receiving_two_way': direction == 'two_way',
              'approach_direction_xy': [1, 0], 'receiving_direction_xy': [0, 1],
              'approach_reference_xy': [0, 0],
              'approach_lane_centers_xy': {'inner': [0, 0], 'left': [0, 3.5]},
              'extreme_left_lane_id': 'left',
              'signal': {'official': True, 'head_configuration': 'steady_red_alone',
                         'native_actor_id': 'fixture-signal'},
              'stop_reference': {'kind': 'marked_crosswalk',
                                 'hierarchy_reviewed': True, 'point_xy': [10, 0]}}
    packet_path = location / 'site-packet.json'
    write(packet_path, packet)
    history = location / 'history.jsonl'
    if kind != 'missing_evidence':
        lane = 'inner' if case['draft_variables']['approach_position'] == 'inner_lane' else 'left'
        lateral = 0 if lane == 'inner' else 3.5
        centers = [7, 8, 10] if kind == 'complete_motion' else [7, 8, 8]
        rows = []
        for index, center in enumerate(centers):
            native = {'origin': 'native_world_snapshot', 'frame': index,
                      'time_s': index / 20, 'signal_actor_id': 'fixture-signal',
                      'signal_state': 'steady_red_alone',
                      'ego': {'lane_id': lane, 'speed_m_s': 0.0,
                              'body_vertices_xy': [[center-1, lateral-1],
                                                   [center+1, lateral-1],
                                                   [center+1, lateral+1],
                                                   [center-1, lateral+1]]},
                      'directed_participants': []}
            rows.append({'case_id': case['case_id'],
                         'source_packet_sha256': sha(packet_path), 'native_frame': native})
        history.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    return packet_path, history


def run(command: list[str], log: Path, env: dict) -> None:
    process = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(process.stdout.rstrip() + '\n')
    if process.returncode:
        raise ValueError('diagnostic proof failed: ' + process.stdout[-1600:])


def main() -> None:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(REPO / 'runtime') + ':' + str(REPO / 'runtime/scenario_pipeline'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c153046-nov25d/output'),
               TMPDIR=str(REPO / '.runtime-work/c153046-nov25d/tmp'))
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for case, entry in zip(plan['cases'], manifest['cases']):
        suffix = case['case_id'].removeprefix(ROOT.name + '__')
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            location = SCRATCH / (suffix + '-' + kind + '-v8')
            packet, history = fixture(case, kind, location)
            result = ROOT / f'cpu-physical-{suffix}-{kind}-v8.json'
            log = ROOT / f'cpu-physical-{suffix}-{kind}-v8.log'
            command = [sys.executable, str(ROOT / 'physical_probe.py'), '--case',
                       case['case_id'], '--packet', str(packet), '--history', str(history),
                       '--plan', str(ROOT / 'case-plan.json'), '--result', str(result)]
            run(command, log, env)
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log.name, 'log_sha256': sha(log),
                             'result': result.name, 'result_sha256': sha(result)})
        lifecycle_log = ROOT / f'cpu-lifecycle-{suffix}-v8.log'
        lifecycle_command = [sys.executable, str(ROOT / 'prove_lifecycle.py'),
                             '--case', case['case_id'], '--construction',
                             str(ROOT / entry['construction']), '--scratch',
                             str(SCRATCH / (suffix + '-lifecycle-v8'))]
        run(lifecycle_command, lifecycle_log, env)
        events = json.loads(lifecycle_log.read_text())['events']
        receipt = {'format': 'worker-red-left-physical-diagnostic-proof',
                   'case_id': case['case_id'], 'construction_sha256': entry['construction_sha256'],
                   'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
                   'fixtures': fixtures,
                   'lifecycle': {'command': ' '.join(lifecycle_command), 'exit_code': 0,
                                 'events': events, 'log': lifecycle_log.name,
                                 'log_sha256': sha(lifecycle_log),
                                 'original_owner_release_claimed': False}}
        receipt_path = ROOT / f'cpu-physical-{suffix}-receipt.json'
        write(receipt_path, receipt)
        entry['physical_preparation'] = {'receipt': receipt_path.name,
                                         'sha256': sha(receipt_path)}
        print('physical diagnostic passed:', suffix, flush=True)
    write(ROOT / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    main()
