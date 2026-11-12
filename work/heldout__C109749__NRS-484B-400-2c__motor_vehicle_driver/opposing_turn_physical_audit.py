"""Saved-original motion completion check; never decides statutory passing order."""
import hashlib
import json
from pathlib import Path

from opposing_turn_measurement import measure

LIFECYCLE = ('capture_finished','encoders_closed','restoration_verified',
             'native_exit','owner_released','saved_processing_started')


def validate_lifecycle(events):
    if tuple(events) != LIFECYCLE:
        raise ValueError('saved processing must follow Native exit and owner release')
    return True


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def assess(subject, opposing, topology, devices, source_kind='diagnostic'):
    paths = [Path(p) for p in (subject, opposing, topology, devices)]
    refs = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in paths if p.is_file()]
    base = {'method': 'joined original body and map/device histories; require both actors before, during and after one left-turn interval',
            'sources': refs}
    if len(refs) != 4:
        status = 'unverified'
        observations = {}
    else:
        try:
            geometry = measure(*paths)
            a, b = _rows(paths[0]), _rows(paths[1])
            joined = len(a) == len(b) and all(x['frame'] == y['frame'] for x, y in zip(a, b))
            entered = any(x.get('in_intersection') and y.get('in_intersection') and
                          x.get('turning_left') and y.get('turning_left') for x, y in zip(a, b))
            before = bool(a and b and not a[0].get('in_intersection') and not b[0].get('in_intersection'))
            after = bool(a and b and not a[-1].get('in_intersection') and not b[-1].get('in_intersection'))
            motion = all(x.get('center_xy') != y.get('center_xy') for x, y in
                         ((a[0], a[-1]), (b[0], b[-1])))
            complete = joined and entered and before and after and motion and source_kind == 'native'
            status = 'met' if complete else 'not_met'
            observations = {'simultaneous_frames': geometry['simultaneous_frames'],
                            'before_junction': before, 'after_junction': after,
                            'both_moved': motion, 'joined': joined}
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            status = 'unverified'
            observations = {}
    base['status'] = status
    return {'physical_checks': {'maneuver': base}, 'maneuver_completed': status == 'met',
            'realized_observables': observations if status == 'met' else {},
            'provenance_kind': source_kind,
            'legal_front_of_each_other': 'unreviewed'}
