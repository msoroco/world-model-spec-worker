"""Compare two original, reviewed-site pedestrian Native attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit_pair
from device_timeline import observe_timeline
from native_crossing import measure, source
from production_delivery_audit import ASSIGNMENT, verify


ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def summary(case_id: str, attempt: Path) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    verify(case_id, attempt)
    receipt = json.loads((attempt / 'capture-receipt.json').read_text())
    site = json.loads((attempt / 'site-source.json').read_text())
    refs = {Path(ref['path']).name: ref for ref in site['original_sources']}
    map_path = site['map_source_path']
    head_path = site['signal_source_path']
    device_path = site['device_inventory_source_path']
    for name in (map_path, head_path, device_path):
        if Path(name).name not in refs:
            raise ValueError('reviewed comparison source missing: ' + name)
    map_source = json.loads(source(refs[Path(map_path).name], attempt).read_text())
    normalized_map = {key: value for key, value in map_source.items()
                      if key not in ('crosswalk_kind', 'crosswalk_qualifies')}
    facts = measure(site, attempt, receipt['original_frames'])
    timeline = observe_timeline(facts)
    config = json.loads((attempt / 'config.json').read_text())
    camera = config['cameras']
    first = facts['measurements'][0]
    return {
        'case_suffix': case_id.removeprefix(ASSIGNMENT + '__'),
        'map_source_sha256': digest(normalized_map),
        'signal_source_sha256': sha(source(refs[Path(head_path).name], attempt)),
        'device_inventory_source_sha256': sha(source(refs[Path(device_path).name], attempt)),
        'highway_polygon_source_sha256': digest(site['highway_polygon_xy']),
        'camera_profile_sha256': digest([(x['name'], x['width'], x['height']) for x in camera]),
        'duration_frames': facts['frame_count'],
        'crosswalk_kind': facts['crosswalk_kind'],
        'green_alone_frames': sum(bool(row['green_alone']) for row in facts['measurements']),
        'first_highway_entry': facts['first_highway_entry'],
        'device_indication_while_waiting': first['other_device_indication'],
        'device_timeline': timeline, 'source_bound': True,
        'diagnostic_fixture': False,
        'source_refs': {'site-source.json': sha(attempt / 'site-source.json'),
                        'original-frames.json': sha(attempt / 'original-frames.json')},
    }


def run(comparison_id: str, left: Path, right: Path) -> dict:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    match = next((item for item in plan['comparisons']
                  if item['comparison_id'] == comparison_id), None)
    if match is None or len(match['case_ids']) != 2:
        raise ValueError('unknown exact comparison')
    left_id, right_id = match['case_ids']
    result = audit_pair(comparison_id, summary(left_id, left), summary(right_id, right))
    if result.get('physical_acceptance') is not False or result.get('legal_verdict') is not None:
        raise ValueError('comparison asserted unsupported acceptance')
    return {'format': 'worker-pedestrian-production-comparison',
            'comparison_id': comparison_id, 'case_ids': [left_id, right_id],
            'observations': result, 'physical_acceptance': False,
            'legal_verdict': None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.comparison, args.left, args.right), sort_keys=True))


if __name__ == '__main__':
    main()
