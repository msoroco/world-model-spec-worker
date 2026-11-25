"""Materialize the canonical first exact construction and root configuration."""
from __future__ import annotations

import json
from pathlib import Path
from overpass_source import sha

ROOT = Path(__file__).resolve().parent


def main():
    source = ROOT / 'cases/yield_before_vehicle/construction.json'
    construction = json.loads(source.read_text())
    construction.update({
        'measurement_plan': {name: 'Source-bound original Native measurement; legal judgment unresolved'
                             for name in ('crossing_order', 'roadway_vehicle_inventory',
                                          'provided_overhead_crossing', 'designated_place_prohibition')},
        'static_checks': ['exact source-hashed overpass and scene',
                          'four Native camera joins and complete video decode',
                          'reviewed original site and municipal designation source'],
        'termination_rules': {'duration_s': 45.0,
                              'early_termination': 'retain failed unsealed original attempt'},
        'mechanisms': ['source-hashed surface roadway and elevated deck candidate',
                       'Native walker and all-roadway-vehicle state recording',
                       'four original frame-joined camera views'],
        'source_scene_sha256': sha(ROOT / 'scene-yield_before_vehicle.json'),
        'source_map_sha256': sha(ROOT / 'candidate-overpass.xodr')})
    for item in construction['files']:
        if not item.get('source'):
            path = ROOT / item['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item['content'])
    (ROOT / 'scene.json').write_bytes((ROOT / 'scene-yield_before_vehicle.json').read_bytes())
    (ROOT / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')


if __name__ == '__main__':
    main()
