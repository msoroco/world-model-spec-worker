"""Saved-only pedestrian/arrow measurement from sealed original Native packets.

The observed WALK indication is recorded as a fact. Whether it grants statutory
permission under NRS 484B.283 remains a separate review question.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from native_scene import SourceError, measure_attempt, verify_site


ASSIGNMENT = 'testing__C109171__NRS-484B-307-4b__pedestrian'
EXPECTED = {
    'arrow_wait': (False, False),
    'arrow_early_entry': (True, False),
    'arrow_walk_entry': (True, True),
    'arrow_walk_wait': (False, True),
    'permission_applicability-0000': (True, True),
    'permission_applicability-0001': (True, True),
    'permission_applicability-0002': (True, True),
    'permission_applicability-0003': (True, True),
}
SWEEP_ENTRY_DELAY_TICKS = {
    'permission_applicability-0000': 20,
    'permission_applicability-0001': 80,
    'permission_applicability-0002': 40,
    'permission_applicability-0003': 60,
}


def _require(condition, message):
    if not condition:
        raise SourceError(message)


def _read_ref(root, ref):
    root = Path(root).resolve()
    path = (root / ref['path']).resolve()
    _require(path.is_relative_to(root), 'source escapes attempt root')
    _require(path.is_file(), 'missing original source')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _require(digest == ref['sha256'], 'source hash mismatch')
    return json.loads(path.read_text(encoding='utf-8'))


def measure_saved(root, site_ref, events_ref, case_id, expected_frames=900):
    """Return sourced observations for one exact 20 Hz case, without a verdict."""
    _require(case_id.startswith(ASSIGNMENT + '__'), 'case outside assignment')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    _require(suffix in EXPECTED, 'unknown exact case')
    _require(isinstance(expected_frames, int) and expected_frames > 1, 'invalid frame count')
    site = _read_ref(root, site_ref)
    _require(isinstance(site, dict), 'site packet must be an object')
    _require(site.get('source_kind') == 'native_original', 'diagnostic site packet rejected')
    verify_site(site, root)
    rows = _read_ref(root, events_ref)
    _require(isinstance(rows, list) and len(rows) == expected_frames, 'incomplete original frame history')
    measured = measure_attempt(site, root, events_ref)
    want_entry, want_walk = EXPECTED[suffix]
    entry = measured['first_highway_entry']
    _require((entry is not None) == want_entry, 'entry behavior differs from exact case')
    if suffix in SWEEP_ENTRY_DELAY_TICKS:
        _require(entry['frame'] >= SWEEP_ENTRY_DELAY_TICKS[suffix],
                 'sweep entry precedes authored controller delay')
    walk_frames = []
    for index, row in enumerate(rows):
        _require(row.get('frame') == index, 'frame identity mismatch')
        t = row.get('sim_time_seconds')
        _require(isinstance(t, (int, float)) and math.isfinite(t), 'missing finite original time')
        if index:
            previous = rows[index-1]['sim_time_seconds']
            _require(abs((t-previous)-0.05) < 1e-4, 'original 20 Hz time join failed')
        indication = row.get('pedestrian_device_indication')
        _require(indication in {'WALK', 'DONT_WALK', 'FLASHING_DONT_WALK'},
                 'unknown original pedestrian indication')
        if indication == 'WALK':
            walk_frames.append(index)
    _require(bool(walk_frames) == want_walk, 'separate device timeline differs from exact case')
    if want_entry and want_walk:
        _require(walk_frames[0] < entry['frame'], 'separate WALK did not precede measured entry')
        _require(entry['separate_walk_indication'] is True,
                 'separate WALK absent at measured entry')
    if want_entry and not want_walk:
        _require(entry['separate_walk_indication'] is False,
                 'unexpected separate WALK at measured entry')
    return {
        'format': 'c109171-saved-measurement-v1',
        'assignment_id': ASSIGNMENT,
        'case_id': case_id,
        'frame_count': expected_frames,
        'fps': 20,
        'sole_green_arrow_frames': measured['sole_green_arrow_frames'],
        'first_highway_entry': entry,
        'first_highway_entry_time_s': entry['frame'] / 20 if entry is not None else None,
        'separate_walk_first_frame': walk_frames[0] if walk_frames else None,
        'separate_walk_frame_count': len(walk_frames),
        'original_site_sha256': site_ref['sha256'],
        'original_events_sha256': events_ref['sha256'],
        'original_source_refs': [site_ref, events_ref] + site['original_sources'],
        'physical_acceptance': False,
        'legal_verdict': None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--site-ref', type=Path, required=True)
    parser.add_argument('--events-ref', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--expected-frames', type=int, default=900)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    site_ref = json.loads(args.site_ref.read_text(encoding='utf-8'))
    events_ref = json.loads(args.events_ref.read_text(encoding='utf-8'))
    result = measure_saved(args.attempt, site_ref, events_ref, args.case_id, args.expected_frames)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
