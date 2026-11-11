"""Add original body-extents and closing-rate time-to-conflict to safety pair."""
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')


for slug, offset in (('safety_wide', 8.0), ('safety_narrow', 3.0)):
    folder = ROOT / 'cases' / slug
    construction = json.loads((folder / 'construction.json').read_text())
    description = construction['recording_description']
    description['channels'] += [
        {'name': 'participant_clearance_m', 'unit': 'm', 'method': 'original planar center separation minus Native rider and participant half-widths', 'sampling_rate_hz': 20,
         'time_window': 'all original frames', 'reference_frame': 'Native world XY joined to original frame map', 'uncertainty': 'projected half-width approximation; physical actor visibility and legal safety unverified'},
        {'name': 'time_to_conflict_s', 'unit': 's', 'method': 'original consecutive-frame closing rate to combined Native body half-widths', 'sampling_rate_hz': 20,
         'time_window': 'frames with measured closure', 'reference_frame': 'Native world XY and original frame time', 'uncertainty': 'local linear closing-rate prediction; not a legal safety threshold'}]
    description['limitations'].append('The participant walker crosses toward the rider path at 1 m/s; finite closing-rate estimates require original position and body extent readback.')
    files = {item['path']: item for item in construction['files']}
    for name in ('rider_participant.py','rider_clearance_measurement.py'):
        files[name]['content'] = (ROOT / name).read_text()
    for name in ('runner.py','native_rider_probe.py'):
        source = files[name]['content']
        old = 'participant_recorder.capture(frame, time_s, trace, participant)'
        assert old in source
        files[name]['content'] = source.replace(old,'participant_recorder.capture(frame, time_s, trace, participant, bicycle)')
    for name in ('config.json','probe-config.json'):
        config = json.loads(files[name]['content'])
        config['case']['recording_description'] = description
        files[name]['content'] = json.dumps(config, indent=2) + '\n'
    source = files['tests/test_rider_signal_finalizer.py']['content']
    old = f"'actor_id': 'other-1', 'position_m': [float(i), {int(offset)}.0, 0.0]}} for i in range(4)]"
    new = f"'actor_id': 'other-1', 'position_m': [float(i), {int(offset)}.0 - i * .05, 0.0], 'rider_half_width_m': .45, 'participant_half_width_m': .35}} for i in range(4)]"
    assert old in source, old
    source = source.replace(old, new)
    old = f"'participant_actor_id': 'other-1', 'center_distance_m': {int(offset)}.0}} for i in range(4)]"
    new = f"'participant_actor_id': 'other-1', 'center_distance_m': {int(offset)}.0 - i * .05}} for i in range(4)]"
    assert old in source
    files['tests/test_rider_signal_finalizer.py']['content'] = source.replace(old,new)
    source = files['rider_signal_finalizer.py']['content']
    marker = "    result['physical_acceptance_claimed'] = False\n    result['legal_acceptance_claimed'] = False\n    return result\n"
    assert marker in source
    addition = '''    participant_rows = [json.loads(line) for line in (Path(attempt) / 'participant_motion.jsonl').read_text().splitlines() if line.strip()]
    body_path = Path(attempt) / 'participant_clearance_m.jsonl'
    if body_path.exists():
        raise ValueError('Retain prior derived body clearance channel')
    body_path.write_text(''.join(json.dumps({'frame': sample['frame'], 'time_s': sample['time_s'],
        'value': max(0.0, sample['center_distance_m'] - other['rider_half_width_m'] - other['participant_half_width_m'])}) + '\\n'
        for sample, other in zip(samples, participant_rows)))
    result['recording_evidence'].append({'name': 'participant_clearance_m', 'unit': 'm',
        'reference': 'participant_clearance_m.jsonl', 'sha256': sha256(body_path.read_bytes()).hexdigest()})
    result['realized_observables']['participant_clearance_m'] = {
        'unit': 'm', 'method': 'original planar center separation minus Native body half-widths',
        'time_window': 'all original frames', 'statistic': 'minimum',
        'reference': 'participant_clearance_m.jsonl',
        'value': result['measured_values']['rider_clearance_observation']['minimum_body_footprint_clearance_m'],
        'sample_window_s': [samples[0]['time_s'], samples[-1]['time_s']]}
    predictions = result['measured_values']['rider_clearance_observation']['time_to_conflict_prediction_samples']
    if not predictions:
        raise ValueError('No measured closing-rate time to conflict')
    ttc_path = Path(attempt) / 'time_to_conflict_s.jsonl'
    if ttc_path.exists():
        raise ValueError('Retain prior derived conflict-time channel')
    ttc_path.write_text(''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
        'value': row['time_to_conflict_s']}) + '\\n' for row in predictions))
    result['recording_evidence'].append({'name': 'time_to_conflict_s', 'unit': 's',
        'reference': 'time_to_conflict_s.jsonl', 'sha256': sha256(ttc_path.read_bytes()).hexdigest()})
    result['realized_observables']['time_to_conflict_s'] = {
        'unit': 's', 'method': 'original consecutive-frame closing rate to Native body half-widths',
        'time_window': 'frames with measured closure', 'statistic': 'minimum',
        'reference': 'time_to_conflict_s.jsonl',
        'value': result['measured_values']['rider_clearance_observation']['time_to_conflict_s'],
        'sample_window_s': [predictions[0]['time_s'], predictions[-1]['time_s']]}
'''
    source = source.replace(marker,addition+marker)
    files['rider_signal_finalizer.py']['content'] = source
    save(folder / 'construction.json', construction)
    diagnostic = json.loads((folder / 'diagnostic-input.json').read_text())
    trace = [json.loads(line) for line in diagnostic['files']['trace.jsonl'].splitlines() if line]
    motion, clearance = [], []
    for row in trace:
        point = row['position_m']
        other = [float(point[0]), float(point[1])+offset-float(row['time_s']), float(point[2])]
        distance = hypot(float(point[0])-other[0], float(point[1])-other[1])
        motion.append({'frame': row['frame'], 'time_s': row['time_s'],
                       'actor_id': 'diagnostic-participant-1', 'position_m': other,
                       'rider_half_width_m': .45, 'participant_half_width_m': .35})
        clearance.append({'frame': row['frame'], 'time_s': row['time_s'],
                          'participant_actor_id': 'diagnostic-participant-1',
                          'center_distance_m': distance})
    diagnostic['files']['participant_motion.jsonl']=''.join(json.dumps(row)+'\n' for row in motion)
    diagnostic['files']['clearance_samples.jsonl']=''.join(json.dumps(row)+'\n' for row in clearance)
    save(folder/'diagnostic-input.json',diagnostic,compact=True)
    spec=json.loads((folder/'diagnostic-recipe.json').read_text())
    checksum=sha256((folder/'diagnostic-input.json').read_bytes()).hexdigest()
    spec['sources'][0]['sha256']=checksum
    spec['generator']['sha256']=checksum
    save(folder/'diagnostic-recipe.json',spec)
    print(slug,'original body geometry and closing-rate construction upgraded')
