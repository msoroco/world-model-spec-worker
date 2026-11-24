"""Selected-requirement measurements from sealed original approach sources.

These values describe observed geometry and motion. They do not decide whether
an approach satisfies the statute's nearest-centerline phrase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from approach import _verified, measure, validate_context

SOURCES = ('intersection-context.json', 'approach-history.jsonl',
           'video_frames.jsonl')


def _source(attempt: Path):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    originals = {}
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
        path, digest = _verified(attempt, name, acquisition)
        originals[name] = {'path': path, 'sha256': digest}
    return acquisition, originals


def measure_left_turn(attempt: Path) -> dict:
    observed = measure(attempt)
    return {'approach_frames': len(observed['approach_frames']),
            'departure_frames': len(observed['departure_frames']),
            'left_turn_heading_change_rad': observed['observed_left_turn_heading_change_rad']}


def measure_two_directional(attempt: Path) -> dict:
    _, originals = _source(attempt)
    context = json.loads(originals['intersection-context.json']['path'].read_text())
    validate_context(context)
    return {'road_ids': [road['road_id'] for road in context['intersecting_roads']],
            'lane_counts': [len(road['lanes']) for road in context['intersecting_roads']],
            'public_highway_source': context['public_highway_source']}


def measure_right_half(attempt: Path) -> dict:
    observed = measure(attempt)
    return {'centerline_kind': observed['centerline_kind'],
            'nearest_body_edge_range_m': observed['nearest_body_edge_range_m'],
            'all_sampled_body_in_right_half': observed['all_sampled_body_in_right_half']}


def finalize(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    acquisition, originals = _source(attempt)
    if acquisition.get('case_id') != case_id:
        raise ValueError('wrong exact saved case')
    hashes = {name: row['sha256'] for name, row in originals.items()}
    values = {}
    for key, method in (('left_turn_observed', measure_left_turn),
                        ('two_directional_roads', measure_two_directional),
                        ('approach_right_half', measure_right_half)):
        values[key] = {'method': method.__name__, 'value': method(attempt),
                       'sources': hashes}
    return {'case_id': case_id, 'measurements': values,
            'source_complete': True, 'legal_nearest_portion_verdict': 'unresolved',
            'acquisition_sha256': hashlib.sha256((attempt / 'acquisition.json').read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('refusing to overwrite saved output')
    acquisition = json.loads((args.attempt / 'acquisition.json').read_text())
    case_id = acquisition.get('case_id')
    if not isinstance(case_id, str) or not case_id:
        raise ValueError('original acquisition case missing')
    report = finalize(args.attempt, case_id)
    with args.output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
