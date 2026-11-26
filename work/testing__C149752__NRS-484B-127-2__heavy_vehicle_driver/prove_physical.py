"""Exercise synthetic motion states and ordered Native/saved lifecycle."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

from truck_following import CASES, audit_original_frames
from native_packet import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c149752/physical'
output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
if ROOT / '.runtime-work' not in output_root.parents:
    raise ValueError('Pipeline output must remain under .runtime-work')
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def probe(entry, case, kind):
    root = SCRATCH / case.suffix / kind
    root.mkdir(parents=True, exist_ok=True)
    construction = json.loads((HERE / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    write(root / 'config.json', config)
    write(root / 'acquisition-provenance.json',
          {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    frames = [{'video_frame': i, 'carla_frame': 100 + i, 'time_s': i / 20}
              for i in range(900)]
    (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n'
                                                  for row in frames), encoding='utf-8')
    if kind != 'missing_evidence':
        positions = [i * .25 for i in range(900)] if kind == 'complete_motion' else [0.0] * 900
        trace = [{'frame': 100 + i, 'time_s': i / 20,
                  'position_m': [value, 0.0, 0.0]} for i, value in enumerate(positions)]
        (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n'
                                               for row in trace), encoding='utf-8')
        (root / 'truck_context.json').write_text('{}\n', encoding='utf-8')
        truck_rows = []
        for i, position in ((0, positions[0]), (899, positions[-1])):
            truck_rows.append({'frame': 100 + i, 'time_s': i / 20,
                'ego_vertices_m': [[position + dx, dy] for dx, dy in
                                   ((0, 0), (1, 0), (1, 1), (0, 1))],
                'lead_vertices_m': [[position + 20 + dx, dy] for dx, dy in
                                    ((0, 0), (1, 0), (1, 1), (0, 1))]})
        (root / 'truck_history.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in truck_rows), encoding='utf-8')
    result = physical_result(root, {'target_checks': []})
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if (result['physical_checks']['maneuver']['status'] != expected or
            result['maneuver_completed'] != (expected == 'met')):
        raise ValueError('synthetic physical motion state differs from assessor')
    target = HERE / 'physical' / case.suffix / (kind + '-result.json')
    write(target, result)
    log = HERE / 'physical' / case.suffix / (kind + '-proof.log')
    log.write_text('synthetic truck-motion assessment: ' + expected + '\n', encoding='utf-8')
    return {'kind': kind, 'command': 'prove_physical.py ' + case.suffix + ' ' + kind,
            'exit_code': 0, 'log': str(log.relative_to(HERE)),
            'log_sha256': sha(log), 'result': str(target.relative_to(HERE)),
            'result_sha256': sha(target)}


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    if not (events.index('restoration_verified') < events.index('native_exit') <
            events.index('owner_released') < events.index('saved_processing_started')):
        raise ValueError('saved processing cannot precede Native closure')
    for case in CASES:
        entry = entries[AID + '__' + case.suffix]
        history_path = HERE / 'diagnostics' / case.suffix / 'original-truck-history.jsonl'
        history = [json.loads(line) for line in history_path.read_text().splitlines()]
        measured = audit_original_frames({'source_kind': 'sealed_native_original_frames',
            'case_id': entry['case_id'], 'frames': history}, case_id=entry['case_id'])
        if measured['original_frame_count'] != 900:
            raise ValueError('synthetic truck measurement is incomplete')
        fixtures = [probe(entry, case, kind) for kind in
                    ('complete_motion', 'incomplete_motion', 'missing_evidence')]
        log = HERE / 'physical' / case.suffix / 'lifecycle.log'
        log.write_text('\n'.join(events) + '\n', encoding='utf-8')
        receipt = {'format': 'c149752-synthetic-physical-preparation',
            'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'fixtures': fixtures,
            'target_truck_observation': {'frames': measured['original_frame_count'],
                'steady_gap_min_m': measured['steady_gap_min_m'],
                'subject_width_min_m': measured['subject_width_min_m'],
                'lead_width_min_m': measured['lead_width_min_m'],
                'same_direction_lanes': measured['same_direction_available_lane_count_min'],
                'source': str(history_path.relative_to(HERE)),
                'source_sha256': sha(history_path), 'legal_verdict_claimed': False},
            'lifecycle': {'events': events, 'exit_code': 0,
                          'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}}
        target = HERE / ('physical-' + case.suffix + '-receipt.json')
        write(target, receipt)
        entry['physical_preparation'] = {'receipt': target.name, 'sha256': sha(target)}
        print(case.suffix + ': three synthetic physical states and lifecycle passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
