"""Audit fixed crossing observations and the declared median-footprint difference."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / '.runtime-work/c125714-right-near-compat-v10'
WIDE = REPO / '.runtime-work/c125714-wide-compat-v3'
OUT = ROOT / 'cases/source_verified_wide_separate_crossing'
sys.path.insert(0, str(ROOT))
from median_spacing import check_roadway_pair


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(base=BASE, wide=WIDE):
    fixed = ['road_geometry.json', 'road.xodr', 'crossing_history.jsonl',
             'controller_history.jsonl', 'video_frames.jsonl',
             'capture/evidence.jsonl', 'overview.mkv', 'approach.mkv',
             'reference_corner.mkv', 'driver_reference.mkv']
    for name in fixed:
        if not (base / name).is_file() or not (wide / name).is_file() or sha(base / name) != sha(wide / name):
            raise ValueError('Fixed crossing source differs or is missing: ' + name)
    geometry = json.loads((base / 'road_geometry.json').read_text())
    polygon = geometry['intersection_polygon_xy_m']
    source = 'site-sources/median_spacing_source.json'
    a = check_roadway_pair(json.loads((base / source).read_text()), polygon, 0)
    b = check_roadway_pair(json.loads((wide / source).read_text()), polygon, 0)
    if a['boundary_relation'] != 'below' or b['boundary_relation'] != 'above':
        raise ValueError('Roadway gap does not bracket the 9.144 m geometry prompt')
    if a['roadway_edge_gap_m'] != 1 or b['roadway_edge_gap_m'] != 12:
        raise ValueError('Unexpected measured roadway gaps')
    if b['statutory_crossing_identity'] != 'unresolved':
        raise ValueError('Statutory identity was asserted')
    wide_saved = json.loads((wide / 'analysis-report.json').read_text())
    measured = wide_saved['measurements']['median_crossing_geometry']
    if (measured['value'] != b or
            measured['sources']['median_geometry_source.json'] != sha(wide / 'median_geometry_source.json') or
            sha(wide / 'median_geometry_source.json') != sha(wide / source)):
        raise ValueError('Saved roadway geometry measurement is not source-bound')
    for attempt in (base, wide):
        if json.loads((attempt / 'compatibility.json').read_text()).get('passed') is not True:
            raise ValueError('Compatibility proof incomplete')
    return {'format': 'worker-median-crossing-comparison',
            'fixed_sources': {name: sha(base / name) for name in fixed},
            'roadway_edge_gap_m': {'near': 1, 'wide': 12},
            'declared_difference': 'sourced second roadway footprint and 30-foot geometric relation',
            'statutory_crossing_identity': 'unresolved',
            'physical_acceptance_claimed': False}


def main():
    receipt = audit()
    (OUT / 'comparison-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'fixed_sources': len(receipt['fixed_sources']),
                      'gaps_m': receipt['roadway_edge_gap_m']}))


if __name__ == '__main__':
    main()
