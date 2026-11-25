"""Independent saved-source comparisons for the five exact C111304 pairs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from encounter import CASES
from saved_audit import finalize_saved_measurements


PAIRS = {
    'highway_person_north_timing': ('person_north_early', 'person_north_late'),
    'highway_person_south_timing': ('person_south_early', 'person_south_late'),
    'approach_direction': ('person_north_early', 'person_south_early'),
    'highway_property_position': ('property_near', 'property_far'),
    'premises_person_timing': ('premises_person_early', 'premises_person_late'),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _site(attempt: Path, receipt: dict) -> tuple:
    paths = [attempt / name for name in ('site.json', 'access-review.json', 'access-source.txt')]
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise ValueError('comparison site source missing or redirected')
    site = json.loads(paths[0].read_text(encoding='utf-8'))
    review = json.loads(paths[1].read_text(encoding='utf-8'))
    if (_sha(paths[0]) != receipt.get('site_sha256') or
            _sha(paths[1]) != site.get('public_access_review_sha256') or
            _sha(paths[2]) != review.get('source_sha256')):
        raise ValueError('comparison site source hash mismatch')
    return (site.get('site_id'), site.get('public_access_basis'),
            review.get('public_access_basis'), review.get('source_kind'),
            paths[2].read_bytes())


def _history(attempt: Path) -> list[dict]:
    path = attempt / 'original-history.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def audit(comparison_id: str, left: Path, right: Path) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError('unknown exact comparison')
    expected = PAIRS[comparison_id]
    by_id = {case.case_id: case for case in CASES}
    reports = [finalize_saved_measurements(path, by_id[suffix])
               for path, suffix in zip((left, right), expected)]
    receipts = [json.loads((path / 'native-receipt.json').read_text(encoding='utf-8'))
                for path in (left, right)]
    if any(not report['case_id'].endswith('__' + suffix)
           for report, suffix in zip(reports, expected)):
        raise ValueError('comparison exact case identity differs')
    if _site(left, receipts[0]) != _site(right, receipts[1]):
        raise ValueError('comparison fixed site meaning changed')
    fixed = ('map_sha256', 'camera_plan_sha256', 'public_access_basis',
             'ego_target_speed_mps', 'crossing_target_speed_mps',
             'frame_count', 'original_fps')
    if any(receipts[0].get(key) != receipts[1].get(key) for key in fixed):
        raise ValueError('comparison fixed acquisition condition changed')
    histories = [_history(path) for path in (left, right)]
    fixed_actor = ('ego_blueprint', 'crossing_blueprint', 'property_blueprint',
                   'ego_id', 'crossing_vehicle_id', 'occupant_id',
                   'occupant_vehicle_id')
    if any(histories[0][0].get(key) != histories[1][0].get(key) for key in fixed_actor):
        raise ValueError('comparison fixed actor changed')
    result = {'comparison_id': comparison_id,
              'case_ids': [report['case_id'] for report in reports],
              'native_receipt_sha256': [report['native_receipt_sha256'] for report in reports],
              'original_history_sha256': [report['original_history_sha256'] for report in reports],
              'actual_pixels': False, 'physical_completion': False,
              'legal_judgment': None}
    if comparison_id.endswith('_timing'):
        releases = [receipt['crossing_release_s'] for receipt in receipts]
        distances = [report['measurements']['min_ego_occupant_center_distance_m']
                     for report in reports]
        if releases[0] >= releases[1] or abs(distances[0] - distances[1]) <= 1e-6:
            raise ValueError('comparison release or measured encounter difference missing')
        result.update(crossing_release_s=releases,
                      min_ego_occupant_center_distance_m=distances)
    elif comparison_id == 'highway_property_position':
        if histories[0][0]['property_xy'] == histories[1][0]['property_xy']:
            raise ValueError('comparison property position difference missing')
        distances = [report['measurements']['min_ego_property_center_distance_m']
                     for report in reports]
        if distances[0] >= distances[1]:
            raise ValueError('comparison measured near/far property order missing')
        result['min_ego_property_center_distance_m'] = distances
    else:
        vectors = []
        for rows in histories:
            a, b = rows[0]['ego_xy'], rows[-1]['ego_xy']
            vectors.append((b[0] - a[0], b[1] - a[1]))
        lengths = [math.hypot(*vector) for vector in vectors]
        if min(lengths) <= 1:
            raise ValueError('comparison original ego approach motion missing')
        cosine = sum(a*b for a, b in zip(*vectors)) / (lengths[0]*lengths[1])
        if cosine >= -0.5:
            raise ValueError('comparison observed approach directions not opposed')
        result['direction_cosine'] = cosine
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.left, args.right), sort_keys=True))
