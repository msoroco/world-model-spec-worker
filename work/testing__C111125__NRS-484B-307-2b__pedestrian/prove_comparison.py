"""Audit exact source-shaped diagnostic 900-frame comparison fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from comparison_audit import audit_pair, ComparisonError
from device_timeline import observe_timeline
from native_crossing import measure

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def summary(suffix, scratch):
    repo = ROOT.parents[1]
    origin = repo / '.runtime-work/c111125-owner' / ('selected-compat-' + suffix + '-delivery-v7')
    if not origin.is_dir():
        raise ValueError('selected diagnostic compatibility source missing')
    folder = scratch / suffix
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('map.json', 'head.json', 'devices.json', 'site.json'):
        (folder / name).write_bytes((origin / name).read_bytes())
    first = json.loads((origin / 'frames.json').read_text())
    if len(first) < 3 or first[0]['frame'] != 0 or first[-1]['frame'] != len(first) - 1:
        raise ValueError('diagnostic source sequence differs')
    rows = list(first)
    for frame in range(len(first), 900):
        row = dict(rows[-1])
        row['frame'] = frame
        row['elapsed_seconds'] = frame / 20
        rows.append(row)
    frame_path = folder / 'frames.json'
    frame_path.write_text(json.dumps(rows, separators=(',', ':')) + '\n')
    site = json.loads((folder / 'site.json').read_text())
    facts = measure(site, folder, {'path': 'frames.json', 'sha256': sha(frame_path)})
    timeline = observe_timeline(facts)
    map_source = json.loads((folder / 'map.json').read_text())
    normalized_map = {key: value for key, value in map_source.items()
                      if key not in ('crosswalk_kind', 'crosswalk_qualifies')}
    camera = json.loads((origin / 'config.json').read_text())['cameras']
    return {
        'case_suffix': suffix, 'map_source_sha256': digest(normalized_map),
        'signal_source_sha256': sha(folder / 'head.json'),
        'device_inventory_source_sha256': sha(folder / 'devices.json'),
        'highway_polygon_source_sha256': digest(site['highway_polygon_xy']),
        'camera_profile_sha256': digest([(x['name'], x['width'], x['height']) for x in camera]),
        'duration_frames': 900, 'crosswalk_kind': facts['crosswalk_kind'],
        'green_alone_frames': sum(bool(row['green_alone']) for row in facts['measurements']),
        'first_highway_entry': facts['first_highway_entry'],
        'device_indication_while_waiting': rows[0]['other_device_indication'],
        'device_timeline': timeline, 'source_bound': True,
        'source_refs': {name: sha(folder / name)
                        for name in ('map.json', 'head.json', 'devices.json', 'site.json', 'frames.json')},
        'diagnostic_fixture': True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    repo = ROOT.parents[1]
    if repo / '.runtime-work' not in args.scratch.resolve().parents:
        raise ValueError('scratch must stay under .runtime-work')
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    selected = next((item for item in plan['comparisons']
                     if item['comparison_id'] == args.comparison), None)
    if selected is None:
        raise ValueError('unknown exact comparison')
    left_id, right_id = selected['case_ids']
    left = summary(left_id.removeprefix(ROOT.name + '__'), args.scratch)
    right = summary(right_id.removeprefix(ROOT.name + '__'), args.scratch)
    if args.mode == 'negative':
        right['signal_source_sha256'] = '0' * 64
        audit_pair(args.comparison, left, right)
        raise ValueError('changed fixed signal source was accepted')
    result = audit_pair(args.comparison, left, right)
    if result['legal_verdict'] is not None or result['physical_acceptance'] is not False:
        raise ValueError('comparison asserted acceptance')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True,
                      'source_scope': '900-frame synthetic diagnostic extension',
                      'left_original_frame_sha256': left['source_refs']['frames.json'],
                      'right_original_frame_sha256': right['source_refs']['frames.json'],
                      'fixed_conditions_checked': result['fixed_conditions_checked'],
                      'legal_verdict': None, 'physical_acceptance': False}))


if __name__ == '__main__':
    main()
