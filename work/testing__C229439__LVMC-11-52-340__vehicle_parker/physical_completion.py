"""Assess original parking completion without deciding municipal legal status."""

from __future__ import annotations

from city_space import measure_original


def assess(rows, scene, case, *, diagnostic_frames=None):
    if not rows or not isinstance(scene, dict):
        return {'status': 'unverified', 'reason': 'original parking motion or authority source missing',
                'sources': {}}
    try:
        measured = measure_original(rows, scene, case,
                                    diagnostic_frames=diagnostic_frames)
    except ValueError as error:
        return {'status': 'not_met', 'reason': str(error),
                'sources': {'original_city_space': 'source supplied'}}
    return {'status': 'met', 'reason': 'complete parked interval and original footprint measured',
            'sources': {'original_city_space': 'source supplied'},
            'realized_observables': {'parked_frames': measured['parked_frames'],
                                    'space_overlap': measured['all_footprints_overlap_governed_space']}}


EVENTS = ('capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started')


def verify_lifecycle(events):
    if list(events) != list(EVENTS):
        raise ValueError('saved processing must follow Native exit and owner release')
    return True
