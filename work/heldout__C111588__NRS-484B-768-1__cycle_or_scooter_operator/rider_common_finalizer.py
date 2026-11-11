"""Common saved source channels required by the rider semantic recording plan."""
from hashlib import sha256
import json
from pathlib import Path

from rider_clearance_measurement import measure as measure_clearance
from rider_hand_control import measure as measure_hands


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_channel(root, result, name, unit, rows, method):
    path = root / (name + '.jsonl')
    if path.exists():
        raise ValueError('Retain prior derived common channel: ' + name)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    result['recording_evidence'].append({'name': name, 'unit': unit,
        'reference': path.name, 'sha256': sha256(path.read_bytes()).hexdigest()})
    result['realized_observables'][name] = {'unit': unit, 'method': method,
        'time_window': 'all original frames', 'statistic': 'recorded frames',
        'reference': path.name, 'value': len(rows),
        'sample_window_s': [rows[0]['time_s'], rows[-1]['time_s']]}


def _write_context(root, result, name, unit, value):
    path = root / (name + '.json')
    if path.exists():
        raise ValueError('Retain prior derived common context: ' + name)
    path.write_text(json.dumps({name: value}, indent=2) + '\n')
    result['recording_evidence'].append({'name': name, 'unit': unit,
        'reference': path.name, 'sha256': sha256(path.read_bytes()).hexdigest()})


def enrich(attempt, result):
    root = Path(attempt)
    clearance = measure_clearance(root)
    hand = measure_hands(root)
    motion = _rows(root / 'rider_motion.jsonl')
    mapping = _rows(root / 'video_frames.jsonl')
    contacts = _rows(root / 'hand_contact_review.jsonl')
    stability = _rows(root / 'control_stability.jsonl')
    samples = _rows(root / 'clearance_samples.jsonl')
    participants = _rows(root / 'participant_motion.jsonl')
    if not all(len(rows) == len(mapping) for rows in (motion, contacts, stability, samples, participants)):
        raise ValueError('Common original rider source frame lengths differ')
    if not clearance['time_to_conflict_prediction_samples']:
        raise ValueError('No measured source closing rate for time-to-conflict channel')
    existing = {row['name'] for row in result['recording_evidence']}
    if 'rider_turn_heading_deg' not in existing:
        _write_channel(root, result, 'rider_turn_heading_deg', 'deg',
            [{'frame': row['frame'], 'time_s': row['time_s'], 'value': float(row['rider_yaw_deg'])}
             for row in motion], 'original Native rider yaw readback')
    if 'participant_clearance_m' not in existing:
        _write_channel(root, result, 'participant_clearance_m', 'm',
            [{'frame': sample['frame'], 'time_s': sample['time_s'],
              'value': max(0.0, sample['center_distance_m'] - other['rider_half_width_m'] - other['participant_half_width_m'])}
             for sample, other in zip(samples, participants)],
            'original joined rider/participant positions and body half-widths')
    if 'time_to_conflict_s' not in existing:
        _write_channel(root, result, 'time_to_conflict_s', 's',
            [{'frame': row['frame'], 'time_s': row['time_s'], 'value': row['time_to_conflict_s']}
             for row in clearance['time_to_conflict_prediction_samples']],
            'original consecutive-frame closing rate to combined Native body half-widths')
    _write_channel(root, result, 'rider_hand_contact', 'categorical',
        [{'frame': row['frame'], 'time_s': row['time_s'],
          'value': ('both_visible' if row['left_hand_contact'] is True and row['right_hand_contact'] is True
                    else 'not_both_visible' if row['left_hand_contact'] is not None and row['right_hand_contact'] is not None
                    else 'unreviewed')}
         for row in contacts], 'original source-video hand-contact review')
    _write_channel(root, result, 'rider_control_stability', 'structured_record',
        [{'frame': row['frame'], 'time_s': row['time_s'],
          'value': {key: value for key, value in row.items() if key not in ('frame','time_s')}}
         for row in stability], 'original Native control/steering readback')
    context = json.loads((root / 'rider_context.json').read_text())
    route = json.loads((root / 'route_waypoints.json').read_text())
    if not route.get('waypoints') or len(route['waypoints']) < 3:
        raise ValueError('Original turn-path waypoints missing')
    device = context.get('device_type')
    _write_context(root, result, 'rider_device_class', 'categorical',
        'candidate_' + device if device else 'unreviewed')
    _write_context(root, result, 'rider_roadway_status', 'categorical',
        'candidate_roadway' if context.get('on_roadway') is True else 'unreviewed')
    _write_context(root, result, 'turn_path_geometry', 'structured_record', route)
    result['measured_values']['common_source_observation'] = {
        'minimum_body_footprint_clearance_m': clearance['minimum_body_footprint_clearance_m'],
        'time_to_conflict_s': clearance['time_to_conflict_s'],
        'hand_contact_review_complete': hand['hand_contact_review_complete'],
        'legal_reasonable_safety_judgment': None}
    result['physical_acceptance_claimed'] = False
    result['legal_acceptance_claimed'] = False
    return result
