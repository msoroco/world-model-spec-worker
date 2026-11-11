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
    'clearance_narrow': 'clearance-narrow',
    'ped_horn_audio': 'ped-horn',
    'ped_no_horn_audio': 'ped-no-horn',
    'vehicle_hand_signal': 'hand-signal',
    'both_signals': 'both-signals',
    'both_indicator_only': 'both-indicator-only',
}
CHANGED = {
    'reasonable_safety_clearance': {'participant_bodies.jsonl'},
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


def listener_energy(files):
    samples = [sample for row in rows(files, 'ego_signal_audio.jsonl')
               for sample in (row.get('listener_audio_samples') or [])]
    if not samples:
        raise ValueError('Original listener PCM is missing')
    return sum(value * value for value in samples) / len(samples)


def audit(comparison_id, override_case=None, override=None):
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
        values['listener_mean_square'] = [listener_energy(f) for f in (a, b)]
        if not values['listener_mean_square'][0] > values['listener_mean_square'][1]:
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
