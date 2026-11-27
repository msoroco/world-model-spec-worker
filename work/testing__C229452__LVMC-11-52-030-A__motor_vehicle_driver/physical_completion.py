"""Judge physical red-curb halt completion from original motion rows only."""

from math import isfinite


EVENTS = ('capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started')


def evaluate(rows, case_id):
    method = 'original 20 Hz speed, governed curb position and frame identity audit'
    sources = ['original actor trace', 'original red curb context', 'four camera frame map']
    check = {'method': method, 'sources': sources}
    try:
        if len(rows) < 100:
            raise ValueError('fewer than 100 original motion frames')
        previous = -1
        stationary = 0
        for row in rows:
            if row.get('case_id') != case_id or type(row.get('frame')) is not int or row['frame'] <= previous:
                raise ValueError('case or original frame continuity missing')
            previous = row['frame']
            if not all(row.get(key) for key in ('trace_source_sha256', 'curb_source_sha256', 'camera_frame_map_sha256')):
                raise ValueError('original motion or curb/camera source missing')
            speed = row.get('speed_mps')
            if type(speed) not in (int, float) or not isfinite(speed) or speed < 0:
                raise ValueError('original speed measurement missing')
            if speed <= 0.05 and row.get('inside_red_curb') is True:
                stationary += 1
        met = stationary >= 100
        check.update(status='met' if met else 'not_met', stationary_inside_frames=stationary)
        return {'physical_checks': {'maneuver': check}, 'maneuver_completed': met,
                'realized_observables': {'stationary_inside_frames': stationary} if met else {},
                'legal_judgment': None}
    except (ValueError, TypeError, KeyError) as exc:
        check.update(status='unverified', reason=str(exc))
        return {'physical_checks': {'maneuver': check}, 'maneuver_completed': False,
                'realized_observables': {}, 'legal_judgment': None}


def lifecycle(events):
    if tuple(events) != EVENTS:
        raise ValueError('saved processing precedes Native ownership closure')
    return {'events': list(events), 'exit_code': 0}
