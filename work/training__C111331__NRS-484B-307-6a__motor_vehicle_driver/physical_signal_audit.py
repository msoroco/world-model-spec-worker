"""Independent source-row motion and yellow/red entry preparation checks."""
import json
import math
from pathlib import Path


LIFECYCLE = ['capture_finished', 'encoders_closed', 'restoration_verified',
             'native_exit', 'owner_released', 'saved_processing_started']


def check_lifecycle(events):
    if events != LIFECYCLE:
        raise ValueError('Saved processing must follow Native exit and owner release')
    return {'saved_processing_after_owner_release': True}


def classify(samples, frames):
    if len(samples) != 480 or len(frames) != 480:
        return {'status': 'unverified', 'reason': 'Incomplete 480-frame Native/video join'}
    for index, (sample, frame) in enumerate(zip(samples, frames)):
        if (sample.get('request_index') != index or frame.get('video_frame') != index or
                sample.get('native_frame') != frame.get('native_frame') or
                sample.get('native_frame') != frame.get('carla_frame')):
            return {'status': 'unverified', 'reason': 'Broken Native/video frame join'}
    phases = [row.get('observed_signal_state') for row in samples]
    if any(phase not in ('green', 'yellow', 'red') for phase in phases):
        return {'status': 'unverified', 'reason': 'Missing observed signal phase'}
    yellow = next((i for i, p in enumerate(phases) if p == 'yellow'), None)
    red = next((i for i, p in enumerate(phases) if p == 'red'), None)
    if yellow is None or red is None or not 0 < yellow < red:
        return {'status': 'unverified', 'reason': 'No ordered yellow-to-red transition'}
    entry = next((i for i, row in enumerate(samples)
                  if max(point[1] for point in row.get('native_body_xy_m', [])) >= -7), None)
    if entry is None:
        return {'status': 'not_met', 'reason': 'Observed body never entered intersection'}
    first = samples[0]['native_center_xy_m']
    last = samples[-1]['native_center_xy_m']
    displacement = math.dist(first, last)
    if displacement < 20 or last[0] < 20:
        return {'status': 'not_met', 'reason': 'Observed vehicle did not complete route'}
    return {'status': 'met', 'yellow_onset_frame': yellow, 'red_onset_frame': red,
            'full_body_entry_frame': entry, 'phase_at_entry': phases[entry],
            'route_displacement_m': round(displacement, 3)}


def audit_original(folder):
    folder = Path(folder)
    samples = [json.loads(line) for line in (folder / 'native_samples.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (folder / 'video_frames.jsonl').read_text().splitlines()]
    if any(row.get('source_kind') != 'original_native_observation' for row in samples):
        raise ValueError('Original Native signal/body source required')
    result = classify(samples, frames)
    if result['status'] != 'met':
        raise ValueError('Original Native motion incomplete: ' + result['reason'])
    return result
