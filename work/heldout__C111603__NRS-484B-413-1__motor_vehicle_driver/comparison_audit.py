"""Independent original-source comparison audit for five planned turn contrasts."""

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = {
    'vehicle_left_indicator': 'vehicle-indicator',
    'vehicle_no_indicator': 'vehicle-no-indicator',
    'clearance_wide': 'clearance-wide',
    'clearance_mid': 'clearance-mid',
    'clearance_narrow': 'clearance-narrow',
    'indicator_activation_2f': 'indicator-activation-2f',
    'indicator_activation_4f': 'indicator-activation-4f',
    'indicator_activation_6f': 'indicator-activation-6f',
    'ped_horn_audio': 'ped-horn',
    'ped_no_horn_audio': 'ped-no-horn',
    'vehicle_hand_signal': 'hand-signal',
    'both_signals': 'both-signals',
    'both_indicator_only': 'both-indicator-only',
}
CHANGED = {
    'pedestrian_listener_distance': {'participant_bodies.jsonl'},
    'reasonable_safety_clearance': {'participant_bodies.jsonl'},
    'reasonable_safety_scalar_path': {'participant_bodies.jsonl'},
    'indicator_activation_timing': {'ego_signal_audio.jsonl'},
    'pedestrian_horn_audio': {'ego_signal_audio.jsonl', 'listener_audio_original.jsonl', 'horn_actuation.jsonl'},
    'vehicle_indicator': {'ego_signal_audio.jsonl'},
    'vehicle_signal_alternative': {'ego_signal_audio.jsonl', 'hand_signal_original.jsonl'},
    'both_affected_conjunction': {'ego_signal_audio.jsonl', 'listener_audio_original.jsonl', 'horn_actuation.jsonl'},
}
FIXED = {'ego_turn_motion.jsonl', 'turn_originals.jsonl', 'trace.jsonl',
         'video_frames.jsonl', 'turn_scene_context.json', 'affected_participants.json'}


def sha_bytes(data):
    return hashlib.sha256(data.encode()).hexdigest()


def load_case(case_id, override=None):
    suffix = case_id[len(HERE.name) + 2:]
    if suffix not in PREFIX:
        raise ValueError('Unknown selected case: ' + case_id)
    prefix = PREFIX[suffix]
    recipe_path = HERE / f'{prefix}-recipe.json'
    recipe = json.loads(recipe_path.read_text())
    source = ROOT / recipe['generator']['source']
    if hashlib.sha256(source.read_bytes()).hexdigest() != recipe['generator']['sha256']:
        raise ValueError('Stale diagnostic source: ' + case_id)
    data = json.loads(source.read_text())
    files = dict(data['files'])
    if override:
        files.update(override)
    return files, data['videos'], {'path': str(source.relative_to(ROOT)),
                                  'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}


def rows(files, name):
    return [json.loads(line) for line in files[name].splitlines() if line.strip()]


def minimum_gap(files):
    motion = rows(files, 'ego_turn_motion.jsonl')
    bodies = rows(files, 'participant_bodies.jsonl')
    if [x['frame'] for x in motion] != [x['frame'] for x in bodies]:
        raise ValueError('Original clearance frame join differs')
    return min(math.hypot(a['x_m'] - b['bodies']['affected_vehicle']['x_m'],
                          a['y_m'] - b['bodies']['affected_vehicle']['y_m'])
               - a['body_radius_m'] - b['bodies']['affected_vehicle']['body_radius_m']
               for a, b in zip(motion, bodies))


def onset_gap(files):
    motion = rows(files, 'ego_turn_motion.jsonl')
    bodies = rows(files, 'participant_bodies.jsonl')
    first_yaw = motion[0]['ego_yaw_deg']
    onset = next(i for i, row in enumerate(motion)
                 if abs(row['ego_yaw_deg'] - first_yaw) > 1e-6)
    a, b = motion[onset], bodies[onset]['bodies']['affected_vehicle']
    return math.hypot(a['x_m'] - b['x_m'], a['y_m'] - b['y_m']) - a['body_radius_m'] - b['body_radius_m']


def listener_energy(files):
    motion = rows(files, 'ego_turn_motion.jsonl')
    signals = rows(files, 'ego_signal_audio.jsonl')
    packets = rows(files, 'listener_audio_original.jsonl')
    if not motion or not (len(motion) == len(signals) == len(packets)):
        raise ValueError('Original listener PCM frame coverage differs')
    first_yaw = motion[0]['ego_yaw_deg']
    onset = next((i for i, row in enumerate(motion)
                  if abs(row['ego_yaw_deg'] - first_yaw) > 1e-6), None)
    if onset is None or onset == 0:
        raise ValueError('Measured turn onset is absent')
    samples = []
    for movement, signal, packet in zip(motion, signals, packets):
        if movement['frame'] != signal['frame'] or movement['frame'] != packet['frame']:
            raise ValueError('Original listener PCM frame join differs')
        if packet.get('origin') != 'listener_pcm_capture' or packet.get('listener_id') != signal.get('listener_id'):
            raise ValueError('Original listener identity differs')
        source_samples = packet.get('samples')
        if not isinstance(source_samples, list) or not source_samples or any(
                not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in source_samples):
            raise ValueError('Original listener PCM samples are invalid')
        digest = sha_bytes(json.dumps(source_samples, separators=(',', ':')))
        if packet.get('sha256') != digest or signal.get('listener_packet_sha256') != digest or signal.get('listener_audio_samples') != source_samples:
            raise ValueError('Original listener PCM packet hash or signal projection differs')
        if movement['frame'] < motion[onset]['frame']:
            samples.extend(source_samples)
    if not samples:
        raise ValueError('Pre-turn original listener PCM is missing')
    return math.sqrt(sum(value * value for value in samples) / len(samples))


def audit(comparison_id, override_case=None, override=None):
    if comparison_id == 'indicator_activation_timing':
        plan = json.loads((HERE / 'case-plan.json').read_text())
        comparison = next(row for row in plan['comparisons']
                          if row['comparison_id'] == comparison_id)
        cases = comparison['case_ids']
        if [case.rsplit('__', 1)[-1] for case in cases] != [
                'indicator_activation_2f', 'indicator_activation_4f',
                'indicator_activation_6f']:
            raise ValueError('Exact indicator activation cases differ')
        loaded = [load_case(case, override if case == override_case else None)
                  for case in cases]
        fixed = FIXED | {'participant_bodies.jsonl'}
        for name in fixed:
            if any(name not in files or files[name] != loaded[0][0][name]
                   for files, _, _ in loaded):
                raise ValueError('Fixed original indicator source differs: ' + name)
        if any(videos != loaded[0][1] for _, videos, _ in loaded):
            raise ValueError('Fixed four-camera descriptions differ')
        readback = []
        for activation, (files, _, _) in zip((2, 4, 6), loaded):
            signal = rows(files, 'ego_signal_audio.jsonl')
            states = [row['indicator_readback'] for row in signal]
            if states != ['off' if index < activation else 'left'
                          for index in range(len(states))]:
                raise ValueError('Original indicator activation index differs')
            readback.append(states)
        return {'format': 'worker-turn-comparison-audit',
                'comparison_id': comparison_id, 'case_ids': cases,
                'diagnostic_fixture': True,
                'source_refs': [ref for _, _, ref in loaded],
                'fixed_source_sha256': {name: sha_bytes(loaded[0][0][name])
                                        for name in sorted(fixed)},
                'declared_difference_sources': ['ego_signal_audio.jsonl'],
                'measured_values': {'activation_frame_index': [2, 4, 6],
                                    'diagnostic_pre_turn_indicator_frames': [4, 2, 0]},
                'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}
    if comparison_id == 'reasonable_safety_scalar_path':
        plan = json.loads((HERE / 'case-plan.json').read_text())
        comparison = next(row for row in plan['comparisons']
                          if row['comparison_id'] == comparison_id)
        cases = comparison['case_ids']
        if len(cases) != 3 or [case.rsplit('__', 1)[-1] for case in cases] != [
                'clearance_narrow', 'clearance_mid', 'clearance_wide']:
            raise ValueError('Exact clearance scalar points differ')
        loaded = [load_case(case, override if case == override_case else None)
                  for case in cases]
        fixed = FIXED
        for name in fixed:
            if any(name not in files or files[name] != loaded[0][0][name]
                   for files, _, _ in loaded):
                raise ValueError('Fixed original comparison source differs: ' + name)
        if any(videos != loaded[0][1] for _, videos, _ in loaded):
            raise ValueError('Fixed four-camera descriptions differ')
        bodies = [rows(files, 'participant_bodies.jsonl') for files, _, _ in loaded]
        for points in zip(*bodies):
            xy = [(row['bodies']['affected_vehicle']['x_m'],
                   row['bodies']['affected_vehicle']['y_m']) for row in points]
            if xy != [(5, 4), (7, 7), (10, 10)]:
                raise ValueError('Exact affected-vehicle scalar path differs')
        minimum = [minimum_gap(files) for files, _, _ in loaded]
        onset = [onset_gap(files) for files, _, _ in loaded]
        if not (minimum[0] < minimum[1] <= minimum[2] and
                onset[0] < onset[1] < onset[2]):
            raise ValueError('Original clearance scalar measurements differ')
        return {'format': 'worker-turn-comparison-audit',
                'comparison_id': comparison_id, 'case_ids': cases,
                'diagnostic_fixture': True,
                'source_refs': [ref for _, _, ref in loaded],
                'fixed_source_sha256': {name: sha_bytes(loaded[0][0][name])
                                        for name in sorted(fixed)},
                'declared_difference_sources': ['participant_bodies.jsonl'],
                'measured_values': {'placement_scalar_m': [-1, 2, 5],
                                    'minimum_sampled_gap_m': minimum,
                                    'gap_at_turn_onset_m': onset},
                'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}
    if comparison_id == 'pedestrian_listener_distance':
        from listener_sweep_audit import audit as listener_audit
        result = listener_audit()
        points = result['points']
        return {'format': 'worker-turn-comparison-audit', 'comparison_id': comparison_id,
                'case_ids': [item['case_id'] for item in points],
                'diagnostic_fixture': True,
                'source_refs': [{'path': f'listener-{item["offset_m"]}m-diagnostic.json',
                                 'sha256': item['source_sha256']} for item in points],
                'fixed_source_sha256': points[0]['fixed_source_sha256'],
                'declared_difference_sources': ['participant_bodies.jsonl'],
                'measured_values': {'minimum_sampled_ped_gap_m':
                    [item['minimum_sampled_ped_gap_m'] for item in points]},
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparison = next((item for item in plan['comparisons']
                       if item['comparison_id'] == comparison_id), None)
    if comparison is None or comparison_id not in CHANGED or len(comparison['case_ids']) != 2:
        raise ValueError('Unknown two-case turn comparison')
    cases = comparison['case_ids']
    loaded = [load_case(case, override if case == override_case else None) for case in cases]
    (a, av, ar), (b, bv, br) = loaded
    if av != bv:
        raise ValueError('Fixed four-camera diagnostic descriptions differ')
    fixed = FIXED | ({'participant_bodies.jsonl'} if comparison_id != 'reasonable_safety_clearance' else set())
    for name in fixed:
        if name not in a or name not in b or a[name] != b[name]:
            raise ValueError('Fixed original comparison source differs: ' + name)
    changed = CHANGED[comparison_id]
    if not any(a.get(name) != b.get(name) for name in changed):
        raise ValueError('Declared original comparison difference is absent')
    values = {}
    if comparison_id == 'reasonable_safety_clearance':
        values['minimum_sampled_gap_m'] = [minimum_gap(a), minimum_gap(b)]
        if not values['minimum_sampled_gap_m'][0] > values['minimum_sampled_gap_m'][1]:
            raise ValueError('Measured wide/narrow clearance ordering differs')
    elif comparison_id == 'vehicle_indicator':
        values['indicator_readback'] = [sorted({row['indicator_readback'] for row in rows(f, 'ego_signal_audio.jsonl')}) for f in (a, b)]
        if values['indicator_readback'][0] == values['indicator_readback'][1]:
            raise ValueError('Original indicator readback has no contrast')
    elif comparison_id == 'vehicle_signal_alternative':
        if 'hand_signal_original.jsonl' in a or 'hand_signal_original.jsonl' not in b:
            raise ValueError('Hand mechanism source does not distinguish alternatives')
        values['hand_source_frames'] = len(rows(b, 'hand_signal_original.jsonl'))
        if values['hand_source_frames'] != len(rows(b, 'ego_turn_motion.jsonl')):
            raise ValueError('Hand source does not cover the original turn frames')
    else:
        values['pre_turn_listener_rms'] = [listener_energy(f) for f in (a, b)]
        if not values['pre_turn_listener_rms'][0] > values['pre_turn_listener_rms'][1]:
            raise ValueError('Original listener PCM does not show diagnostic horn contrast')
        if 'horn_actuation.jsonl' not in a or 'horn_actuation.jsonl' in b:
            raise ValueError('Horn actuation original differs from comparison policy')
    return {'format': 'worker-turn-comparison-audit', 'comparison_id': comparison_id,
            'case_ids': cases, 'diagnostic_fixture': True, 'source_refs': [ar, br],
            'fixed_source_sha256': {name: sha_bytes(a[name]) for name in sorted(fixed)},
            'declared_difference_sources': sorted(changed), 'measured_values': values,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.comparison)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.comparison, 'source_bound_diagnostic_comparison_passed')
