"""Exact fire-lane bundle entrypoint; Native adapter must be locally supplied."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from fire_lane import CASES
from native_capture import capture

ASSIGNMENT = 'testing__C150099__LVMC-11-52-130-A2__motor_vehicle_driver'
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def check(root: Path) -> str:
    config = json.loads((root / 'config.json').read_text())
    raw = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != config.get('plan_sha256'):
        raise ValueError('exact fire-lane plan changed')
    plan = json.loads(raw)
    case_id = config.get('selected_case_id')
    if (config.get('assignment_id'), config.get('cell_id'), config.get('law_id'),
            config.get('actor')) != (ASSIGNMENT, 'C150099',
                                      'LVMC-11-52-130-A2', 'motor_vehicle_driver'):
        raise ValueError('fire-lane identity changed')
    if case_id not in {row['case_id'] for row in plan['cases']}:
        raise ValueError('exact planned case missing')
    case = next((case for case in CASES if case_id == ASSIGNMENT + '__' + case.id), None)
    if case is None:
        raise ValueError('unsupported exact fire-lane case')
    if config.get('case') != vars(case):
        raise ValueError('fire-lane case configuration changed')
    if (config.get('rate_hz'), config.get('frame_count'), config.get('duration_s')) != (20, 900, 45):
        raise ValueError('fire-lane capture duration changed')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError('four-camera configuration missing')
    if [(row.get('name'), row.get('width'), row.get('height')) for row in cameras] != [
            (name, *size) for name, size in zip(NAMES, SIZES)]:
        raise ValueError('four-camera profile changed')
    return case_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--packet', type=Path)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    case_id = check(root)
    if args.check:
        print('exact fire-lane bundle passed: ' + case_id)
        return
    if args.output_dir is None or not args.output_dir.is_dir():
        raise ValueError('executor output directory required')
    packet = args.packet or os.environ.get('SCENARIO_FIRE_LANE_REVIEWED_PACKET')
    if not packet:
        raise ValueError('reviewed original fire-lane site packet required')
    adapter_name = os.environ.get('SCENARIO_FIRE_LANE_NATIVE_ADAPTER')
    if not adapter_name:
        raise ValueError('local Native fire-lane adapter module required')
    adapter = importlib.import_module(adapter_name).open_session(
        case_id, Path(packet), args.host, args.port)
    capture(adapter, case_id, Path(packet), args.output_dir / 'original-attempt')


if __name__ == '__main__':
    main()
