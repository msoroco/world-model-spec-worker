"""Exact C40598 crossing entrypoint; CARLA loads only after source review."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ASSIGNMENT = 'testing__C40598__LVMC-11-30-070-B__pedestrian'
CASE_CATEGORIES = {
    'marked_crosswalk': ('marked', 'frontage_alternative_1'),
    'unmarked_crosswalk': ('unmarked', 'frontage_alternative_1'),
    'outside_both': ('outside', 'frontage_alternative_1'),
    'outside_both_frontage_other': ('outside', 'frontage_alternative_2'),
}
CAMERAS = {'overview': [1920, 1080], 'approach': [1280, 720],
           'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}


def check(root: str | Path) -> dict:
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    spec = json.loads((root / 'case-spec.json').read_text())
    control = json.loads((root / 'controller.json').read_text())
    case_id = config.get('selected_case_id')
    if case_id not in {ASSIGNMENT + '__' + suffix for suffix in CASE_CATEGORIES}:
        raise ValueError('selected business-district case differs')
    if (spec.get('case_id') != case_id or
            (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('LVMC-11-30-070-B', 'C40598', 'pedestrian')):
        raise ValueError('selected business-district law/cell/actor differs')
    named = {row.get('name'): [row.get('width'), row.get('height')]
             for row in config.get('cameras', [])}
    if (config.get('rate_hz') != 20 or config.get('duration_s') != 45 or
            len(config.get('cameras', [])) != 4 or named != CAMERAS):
        raise ValueError('four-camera 20 Hz pedestrian crossing capture differs')
    category, frontage = CASE_CATEGORIES[case_id.split('__')[-1]]
    if (spec.get('crosswalk_category'), spec.get('district_frontage_review')) != (
            category, frontage):
        raise ValueError('selected crosswalk or frontage comparison variable differs')
    speed = control.get('walker_speed_mps')
    if type(speed) not in (int, float) or not 0.3 <= speed <= 1.5:
        raise ValueError('bounded pedestrian crossing controller required')
    return {'case_id': case_id, 'speed': speed,
            'source_gate': 'reviewed original 600-foot business district, roadway, both crosswalk categories, controls and full route required before Native'}


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
    packet = args.packet or os.environ.get('C40598_CROSSING_REVIEW_PACKET')
    source_root = args.source_root or os.environ.get('C40598_CROSSING_SOURCE_ROOT')
    adapter_module = args.adapter_module or os.environ.get('C40598_CROSSING_ADAPTER_MODULE')
    if not packet or not source_root or not adapter_module:
        raise ValueError('original business-district review packet, source root and adapter required')
    from native_entry import run_native
    print(json.dumps(run_native(packet, source_root, adapter_module,
        selected['case_id'], args.output_dir, selected['speed'],
        host=args.host, port=args.port), sort_keys=True))


if __name__ == '__main__':
    main()
