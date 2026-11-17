"""Independent CPU source-join audit for the first school-bus case.

This validates retained bytes and software measurements. It does not certify
equipment, real pupil service, road division, or legal compliance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'runtime'))
from scenario_pipeline.worker_exchange.measurement_contract import verify_report
from scenario_pipeline.worker_exchange.media import audit as decode_video

CASE_ID = 'heldout__C230281__NRS-484B-353-1__motor_vehicle_driver__meeting_stop'
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _timeline(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Independent school-bus timeline empty: ' + Path(path).name)
    return rows


def _join_timeline(attempt, inventory):
    mapping = _timeline(attempt / 'video_frames.jsonl')
    identities = []
    for index, row in enumerate(mapping):
        frame = row.get('carla_frame')
        if (type(frame) is not int or row.get('native_frame') != frame or
                row.get('video_frame') != index or
                type(row.get('time_s')) not in (int, float)):
            raise ValueError('Independent school-bus canonical frame map differs')
        identities.append((frame, row['time_s']))
    if [frame for frame, _ in identities] != inventory.get('frames') or len(set(identities)) != len(identities):
        raise ValueError('Independent school-bus inventory frame order differs')
    for name in ('motion_original.jsonl', 'signal_command_original.jsonl',
                 'pupil_original.jsonl', 'trace.jsonl'):
        rows = _timeline(attempt / name)
        if [(row.get('frame'), row.get('time_s')) for row in rows] != identities:
            raise ValueError('Independent school-bus original timeline differs: ' + name)
    return len(identities)


def audit(attempt, analysis_path, contract_path):
    attempt = Path(attempt)
    report = json.loads(Path(analysis_path).read_text())
    contract = json.loads(Path(contract_path).read_text())
    result = json.loads((attempt / 'result.json').read_text())
    inventory = json.loads((attempt / 'native-acquisition-inventory.json').read_text())
    if any(item.get('case_id') != CASE_ID for item in (report, contract, result, inventory)):
        raise ValueError('Independent school-bus case identity differs')
    if result.get('trace_reference') != 'trace.jsonl' or tuple(result.get('video_references', ())) != VIDEOS:
        raise ValueError('Independent school-bus original source references differ')
    if result.get('video_frame_map_reference') != 'video_frames.jsonl':
        raise ValueError('Independent school-bus frame map reference differs')
    source_hashes = inventory.get('source_sha256')
    if not isinstance(source_hashes, dict) or any(name not in source_hashes for name in
            ('trace.jsonl', 'road.xodr', *VIDEOS)):
        raise ValueError('Independent school-bus inventory incomplete')
    for name, expected in source_hashes.items():
        path = attempt / name
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
        if _hash(path) != expected:
            raise ValueError('Independent school-bus source hash differs: ' + name)
    frames = _join_timeline(attempt, inventory)
    map_sha = _hash(attempt / 'video_frames.jsonl')
    decoded = {name: decode_video(attempt / name, frames, mapping_sha256=map_sha)
               for name in VIDEOS}
    measurements = verify_report(contract, report, attempt)
    response = measurements['stop_response_candidate']['value']
    if not isinstance(response.get('held_stop_until_cessation_candidate'), bool):
        raise ValueError('Independent school-bus stop response missing')
    if result.get('measured_values', {}).get('stop_response_candidate') != response:
        raise ValueError('Independent school-bus Native/analysis response differs')
    if any(result.get(key) is True for key in ('physical_acceptance_claimed', 'legal_acceptance_claimed')):
        raise ValueError('Independent school-bus fixture asserted physical/legal acceptance')
    return {'format': 'worker-school-bus-independent-cpu-audit', 'case_id': CASE_ID,
            'analysis_sha256': _hash(analysis_path), 'native_sha256': _hash(attempt / 'result.json'),
            'inventory_sha256': _hash(attempt / 'native-acquisition-inventory.json'),
            'contract_sha256': _hash(contract_path), 'verified_measurements': sorted(measurements),
            'frame_count': frames,
            'source_decode': {name: {'video_sha256': row['video_sha256'],
                                     'rgb_sequence_sha256': row['rgb_sequence_sha256'],
                                     'dimensions': row['dimensions'], 'frames': row['frames'],
                                     'auditor_sha256': row['auditor_sha256']}
                              for name, row in decoded.items()},
            'software_source_join_passed': True, 'physical_acceptance_claimed': False,
            'legal_conclusion': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--analysis', required=True)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.analysis, args.contract)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
