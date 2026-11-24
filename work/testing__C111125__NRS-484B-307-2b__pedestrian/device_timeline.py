"""Saved frame facts for the NRS 484B.283 device alternatives.

This is a temporal observation, not a determination that a device governs a
crossing or that an entry/continuation was legally permitted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_crossing import measure, source, verify_site


MODES = {'absent', 'walk', 'flashing_countdown', 'flashing_no_countdown',
         'steady', 'unknown'}


def observe_timeline(measured: dict) -> dict:
    facts = measured.get('measurements', [])
    if not facts or measured.get('frame_count') != len(facts):
        raise ValueError('complete original device timeline required')
    ids = [row.get('frame') for row in facts]
    if any(type(value) is not int for value in ids) or ids != list(range(ids[0], ids[0] + len(ids))):
        raise ValueError('original device timeline has a frame gap')
    for row in facts:
        mode = row.get('other_device_mode')
        countdown = row.get('other_device_countdown')
        if mode not in MODES or (mode == 'flashing_countdown' and
                                (type(countdown) is not int or countdown < 0)):
            raise ValueError('original device mode or countdown invalid')
        if mode != 'flashing_countdown' and countdown is not None:
            raise ValueError('countdown outside flashing countdown mode')
        if type(row.get('in_highway')) is not bool or type(row.get('in_crosswalk')) is not bool:
            raise ValueError('original pedestrian region facts required')
    entry = next((i for i, row in enumerate(facts) if row['in_highway']), None)
    if entry == 0:
        raise ValueError('original history starts after highway entry')
    clearance = None
    if entry is not None:
        clearance = next((i for i in range(entry + 1, len(facts))
                          if not facts[i]['in_highway']), None)
        if clearance is not None and any(row['in_highway'] for row in facts[clearance:]):
            raise ValueError('multiple observed highway entry intervals')
    zero = next((i for i, row in enumerate(facts)
                 if row['other_device_mode'] == 'flashing_countdown' and
                 row['other_device_countdown'] == 0), None)
    steady = next((i for i, row in enumerate(facts)
                   if row['other_device_mode'] == 'steady'), None)
    mode_at_entry = None if entry is None else facts[entry]['other_device_mode']
    return {
        'format': 'c111125-saved-device-timeline-v1',
        'original_first_frame': ids[0], 'original_last_frame': ids[-1],
        'entry_frame': None if entry is None else ids[entry],
        'entry_device_mode': mode_at_entry,
        'entry_within_crosswalk': None if entry is None else facts[entry]['in_crosswalk'],
        'clearance_frame': None if clearance is None else ids[clearance],
        'first_countdown_zero_frame': None if zero is None else ids[zero],
        'first_steady_frame': None if steady is None else ids[steady],
        'cleared_before_countdown_zero_observed': None if entry is None or zero is None else
            clearance is not None and clearance < zero,
        'cleared_before_steady_observed': None if entry is None or steady is None else
            clearance is not None and clearance < steady,
        'device_applicability': 'unresolved_requires_reviewed_source',
        'entered_lawfully': None, 'legal_verdict': None,
        'physical_acceptance': False,
    }


def inspect_saved(root: Path, site_ref: dict, events_ref: dict) -> dict:
    root = Path(root).resolve(strict=True)
    site = json.loads(source(site_ref, root).read_text())
    verify_site(site, root)
    measured = measure(site, root, events_ref)
    output = observe_timeline(measured)
    output['site_sha256'] = site_ref['sha256']
    output['original_events_sha256'] = events_ref['sha256']
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt-root', type=Path, required=True)
    parser.add_argument('--site-ref', type=Path, required=True)
    parser.add_argument('--events-ref', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    site_ref = json.loads(args.site_ref.read_text())
    events_ref = json.loads(args.events_ref.read_text())
    result = inspect_saved(args.attempt_root, site_ref, events_ref)
    if args.output.exists():
        raise ValueError('saved timeline output already exists')
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
