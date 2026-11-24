"""Factual parked-interval completion assessment from original body samples."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def assess(attempt: str | Path, *, planned_frames: int,
           diagnostic_fixture: bool = True) -> dict:
    root = Path(attempt)
    names = ('actor-state.jsonl', 'camera-frame-map.jsonl', 'site-packet.json')
    sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
               for name in names if (root / name).is_file()}
    missing = sorted(set(names) - set(sources))
    observed = []
    status = 'unverified'
    reason = 'Required original source is missing' if missing else ''
    if not missing:
        try:
            states = [json.loads(line) for line in (root / names[0]).read_text().splitlines()]
            mapping = [json.loads(line) for line in (root / names[1]).read_text().splitlines()]
            site = json.loads((root / names[2]).read_text())
            if len(states) != planned_frames or len(mapping) != planned_frames or planned_frames < 2:
                raise ValueError('original planned interval incomplete')
            if not site.get('parking_source_ref') or not site.get('intersection_source_ref'):
                raise ValueError('reviewed parking/intersection source absent')
            frames = [row.get('frame') for row in states]
            if frames != list(range(frames[0], frames[0] + planned_frames)):
                raise ValueError('original world frames not contiguous')
            for index, row in enumerate(states):
                if (mapping[index].get('frame') != row['frame'] or
                        any(mapping[index].get(view + '_source_frame') != row['frame']
                            for view in ('overview', 'approach', 'reference_corner', 'driver_reference'))):
                    raise ValueError('original camera frame join differs')
                if index and abs(row['time_s'] - states[index - 1]['time_s'] - .05) > .01:
                    raise ValueError('original 20 Hz time join differs')
                observed.append(row.get('parking_brake') is True and
                                row.get('footprint_inside_reviewed_parking_polygon') is True and
                                isinstance(row.get('speed_mps'), (int, float)) and
                                row['speed_mps'] <= .1)
            status = 'met' if all(observed) else 'not_met'
            reason = 'all source-joined samples parked' if all(observed) else 'a source-joined sample is not parked'
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            status = 'unverified'
            reason = str(error)
    check = {'status': status,
             'method': 'source-joined original body footprint, speed and handbrake interval',
             'sources': sources,
             'intervals': [{'first_frame': 0, 'last_frame': planned_frames - 1}] if observed else [],
             'details': {'planned_frames': planned_frames,
                         'parked_sample_count': sum(observed), 'reason': reason,
                         'engineering_criterion_not_legal': True},
             'missing_evidence': missing,
             'legal_verdict_claimed': False, 'physical_causation_claimed': False}
    return {'physical_checks': {'maneuver': check},
            'maneuver_completed': status == 'met',
            'realized_observables': {'parked_sample_count': sum(observed)} if status == 'met' else {},
            'provenance_kind': 'synthetic_fixture' if diagnostic_fixture else 'native',
            'diagnostic_fixture': diagnostic_fixture,
            'physical_acceptance_claimed': False}
