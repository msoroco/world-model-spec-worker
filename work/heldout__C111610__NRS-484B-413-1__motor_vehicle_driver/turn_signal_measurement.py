"""Original signal timing relative to turn onset; legal standards remain open."""

from hashlib import sha256
import json
from pathlib import Path


def _rows(path):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original signal source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(motion_path, signal_path, frame_map_path, context_path):
    motion, signals, frames = map(_rows, (motion_path, signal_path, frame_map_path))
    context_path = Path(context_path)
    if not context_path.is_file():
        raise ValueError('Missing original affected-user context')
    context = json.loads(context_path.read_text())
    if not context.get('highway_source') or not context.get('turn_route_source'):
        raise ValueError('Highway and direct-course turn source required')
    if not motion or len(motion) != len(signals) or len(motion) != len(frames):
        raise ValueError('Original signal/turn interval incomplete')
    for key in ('pedestrian', 'other_vehicle'):
        user = context.get(key)
        if user is not None and not user.get('position_motion_source'):
            raise ValueError('Affected user needs independent position/motion source')
    observations = []
    for index, (move, signal, frame) in enumerate(zip(motion, signals, frames)):
        identity = (move.get('frame'), move.get('time_s'))
        if (frame.get('video_frame') != index
                or (frame.get('carla_frame'), frame.get('time_s')) != identity
                or (signal.get('frame'), signal.get('time_s')) != identity):
            raise ValueError('Original signal/turn frame join differs')
        if (type(move.get('turning_from_direct_course')) is not bool
                or type(signal.get('horn_command')) is not bool
                or type(signal.get('native_indicator_state')) is not bool):
            raise ValueError('Original turn or Native signal readback missing')
        observations.append({'frame': identity[0], 'time_s': identity[1],
                             'turning': move['turning_from_direct_course'],
                             'horn_command': signal['horn_command'],
                             'native_indicator_state': signal['native_indicator_state']})
    onset = next((row['frame'] for row in observations if row['turning']), None)
    before = [row for row in observations if onset is not None and row['frame'] < onset]
    return {'format': 'worker-turn-signal-original-observation',
            'sources': {Path(p).name: sha256(Path(p).read_bytes()).hexdigest()
                        for p in (motion_path, signal_path, frame_map_path, context_path)},
            'turn_onset_frame': onset,
            'horn_command_before_turn_frames': [row['frame'] for row in before if row['horn_command']],
            'indicator_before_turn_frames': [row['frame'] for row in before
                                             if row['native_indicator_state']],
            'observations': observations,
            'horn_emission_verified': None,
            'horn_audible_at_pedestrian': None,
            'signal_appropriateness': None,
            'reasonable_safety': None,
            'possible_effect': {'pedestrian': None, 'other_vehicle': None}}
