"""Source-deferred original outside-crosswalk pedestrian Native entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ASSIGNMENT = 'testing__C228096__LVMC-11-30-060-A__pedestrian'
CASES = {'yield_with_vehicle': (True, True, False),
         'no_yield_with_vehicle': (True, False, False),
         'yield_no_vehicle': (False, True, False),
         'prohibited_place': (True, True, True)}
CAMERAS = {'overview': [1920, 1080], 'approach': [1280, 720],
           'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}


def check(root: str | Path) -> dict:
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    spec = json.loads((root / 'case-spec.json').read_text())
    control = json.loads((root / 'controller.json').read_text())
    case_id = config.get('selected_case_id')
    if case_id not in {ASSIGNMENT + '__' + suffix for suffix in CASES}:
        raise ValueError('selected outside-crosswalk case differs')
    if (spec.get('case_id') != case_id or
            (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('LVMC-11-30-060-A', 'C228096', 'pedestrian')):
        raise ValueError('selected outside-crosswalk law/cell/actor differs')
    named = {row.get('name'): [row.get('width'), row.get('height')]
             for row in config.get('cameras', [])}
    if (config.get('rate_hz') != 20 or config.get('duration_s') != 45
            or len(config.get('cameras', [])) != 4 or named != CAMERAS):
        raise ValueError('four-camera 20 Hz crossing capture profile differs')
    expected = CASES[case_id.split('__')[-1]]
    actual = (spec.get('requested_vehicle_on_roadway'),
              spec.get('requested_pedestrian_yield'),
              spec.get('requested_prohibited_place_under_11_30_070'))
    if actual != expected:
        raise ValueError('selected crossing comparison variables differ')
    speed = control.get('walker_speed_mps')
    if type(speed) not in (int, float) or not 0.3 <= speed <= 1.5:
        raise ValueError('bounded pedestrian crossing speed required')
    return {'case_id': case_id, 'speed': speed,
            'source_gate': 'reviewed original roadway, both crosswalk categories, vehicles and 11.30.070 place packet required before Native'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=Path.cwd())
    parser.add_argument('--packet', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--adapter-module')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    selected = check(args.output_dir)
    if args.check:
        print(json.dumps({**selected, 'native_started': False}))
        return
    packet = args.packet or os.environ.get('C228096_CROSSING_REVIEW_PACKET')
    source_root = args.source_root or os.environ.get('C228096_CROSSING_SOURCE_ROOT')
    adapter_module = args.adapter_module or os.environ.get('C228096_CROSSING_ADAPTER_MODULE')
    if not packet or not source_root or not adapter_module:
        raise ValueError('external original crossing packet, source root and adapter required')
    from native_entry import run_native
    print(json.dumps(run_native(packet, source_root, adapter_module,
        selected['case_id'], args.output_dir, selected['speed'],
        host=args.host, port=args.port), sort_keys=True))


if __name__ == '__main__':
    main()
