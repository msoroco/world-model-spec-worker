"""Exact-case source-shaped software tests; no original highway claim."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from one_way_direction import CASES
from process_recorded_only import ASSIGNMENT, process


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, separators=(',', ':')) + '\n', encoding='utf-8')


def fixture(attempt: Path, case_id: str) -> dict:
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    case = next((c for c in CASES if c.name == suffix), None)
    if case is None:
        raise ValueError('exact one-way case required')
    if attempt.exists():
        raise ValueError('fresh diagnostic attempt required')
    attempt.mkdir(parents=True)
    source = 'a' * 64
    hashes = {name: source for name in ('highway', 'vehicle', 'driver_control', 'lane_inventory',
              'one_way_designation', 'sign_authority', 'sign_message', 'sign_orientation',
              'sign_placement', 'sign_governance', 'ego_route')}
    sign = 1 if case.direction == 'designated' else -1
    scene = {'cell_id': 'C147311', 'actor': 'motor_vehicle_driver',
             'motor_vehicle': True, 'driver_in_physical_control': True,
             'public_highway': True, 'highway_dedicated': True,
             'one_way_designated': True, 'lane_count': 2, 'lane_ids': [1, 2],
             'lane': case.lane, 'direction': case.direction,
             'sign_authorized': True, 'signposted': True, 'sign_governs_route': True,
             'designated_unit_xy': [1.0, 0.0], 'sign_xy': [0.0, 0.0],
             'ego_route_xy': [[0.0, float(case.lane)], [sign * 225.0, float(case.lane)]],
             'diagnostic_fixture': True}
    scene.update({name + '_source_sha256': value for name, value in hashes.items()})
    write(attempt / 'diagnostic-scene.json', scene)
    fields = ('frame', 'ego_motion', 'ego_position', 'driver_control', 'lane_inventory',
              'one_way_designation', 'sign_authority', 'sign_message',
              'sign_orientation', 'sign_governance')
    with (attempt / 'native-frames.jsonl').open('x', encoding='utf-8') as stream:
        for i in range(900):
            row = {'original_frame': i, 'time_s': i / 20,
                   'ego_id': 'synthetic-ego', 'position_xy': [sign * i * .25, float(case.lane)],
                   'velocity_xy': [sign * 5.0, 0.0], 'lane': case.lane,
                   'sign_governs_route': True,
                   'diagnostic_fixture': True}
            row.update({field + '_source_sha256': source for field in fields})
            stream.write(json.dumps(row, separators=(',', ':')) + '\n')
    return {'case_id': case_id, 'trace_sha256': sha(attempt / 'native-frames.jsonl'),
            'scene_sha256': sha(attempt / 'diagnostic-scene.json')}


def run(root: Path, case_id: str) -> dict:
    source = root / 'attempt'
    fixture_receipt = fixture(source, case_id)
    positive = process(source, root / 'positive', case_id, diagnostic_fixture=True)
    scene = source / 'diagnostic-scene.json'
    data = scene.read_bytes()
    scene.unlink()
    try:
        try:
            process(source, root / 'negative', case_id, diagnostic_fixture=True)
        except ValueError as exc:
            if 'Missing required source: diagnostic-scene.json' not in str(exc):
                raise
            negative_error = str(exc)
        else:
            raise ValueError('missing diagnostic scene was not rejected')
    finally:
        scene.write_bytes(data)
    return {'format': 'c147311-diagnostic-case-compatibility-v1',
            **fixture_receipt, 'positive': positive,
            'negative_expected_error': negative_error,
            'source_kind': 'synthetic_software_fixture',
            'delivery_ready': False}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--case', required=True)
    args = p.parse_args()
    receipt = run(args.output, args.case)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
