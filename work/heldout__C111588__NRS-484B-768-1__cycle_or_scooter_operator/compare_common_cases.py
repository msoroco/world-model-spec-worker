"""Audit seven controlled CPU comparisons against retained exact originals."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
plan = json.loads((ROOT / 'case-plan.json').read_text())
COMMON = ('rider_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl',
          'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
receipts = {}
for row in plan['cases']:
    slug = row['case_id'].rsplit('__', 1)[-1]
    source = REPO / '.runtime-work' / f'c111588-common-{slug}-primary-compat-j'
    receipt = json.loads((source / 'compatibility.json').read_text())
    if not receipt['passed'] or receipt['construction_sha256'] is None:
        raise ValueError(slug + ' compatibility proof did not pass')
    for name in COMMON:
        digest = sha256((source / name).read_bytes()).hexdigest()
        if receipt['fixture_manifest'].get(name) != digest:
            raise ValueError(slug + ' original changed: ' + name)
    receipts[slug] = receipt

def compare(kind, left, right):
    first, second = left['fixture_manifest'], right['fixture_manifest']
    for name in COMMON:
        if first.get(name) != second.get(name):
            raise ValueError(kind + ' fixed original changed: ' + name)
    if kind in ('single_signal', 'continuity_not_required'):
        if first['rider_arm_bones.jsonl'] == second['rider_arm_bones.jsonl']:
            raise ValueError(kind + ' has no arm-command difference')
    elif kind in ('electric_bicycle', 'electric_scooter'):
        if first.get('device_blueprint_readback.json') == second.get('device_blueprint_readback.json'):
            raise ValueError(kind + ' has no device candidate difference')
        observation = right['measurement_examples']['electric_device_observation']['value']
        if observation['device_class_candidate'] != kind or observation['legal_device_class_judgment'] is not None:
            raise ValueError(kind + ' device class claim exceeds originals')
    elif kind == 'turn_lane_exception':
        if first.get('lane_waypoint_readback.jsonl') == second.get('lane_waypoint_readback.jsonl'):
            raise ValueError('Turn-lane candidate has no waypoint difference')
        if right['measurement_examples']['turn_lane_observation']['value']['designated_turn_lane_confirmed'] is not None:
            raise ValueError('Turn-lane designation was not physically reviewed')
    elif kind == 'both_hands_exception':
        if 'both_hands_observation' not in right['measurement_examples'] or 'both_hands_observation' in left['measurement_examples']:
            raise ValueError('Both-hands branch lacks separate measured observation')
        if right['measurement_examples']['both_hands_observation']['value']['both_hands_required_for_safety'] is not None:
            raise ValueError('Both-hands necessity was not physically reviewed')
    elif kind == 'reasonable_safety':
        if first['participant_motion.jsonl'] == second['participant_motion.jsonl']:
            raise ValueError('Safety branches have identical participant motion')
        wide = left['measurement_examples']['rider_clearance_observation']['value']
        narrow = right['measurement_examples']['rider_clearance_observation']['value']
        if not (wide['minimum_center_distance_m'] > narrow['minimum_center_distance_m'] and
                wide['time_to_conflict_s'] > narrow['time_to_conflict_s']):
            raise ValueError('Safety measurement did not respond to participant motion')
    else:
        raise ValueError('Unknown comparison: ' + kind)

results = []
for row in plan['comparisons']:
    kind = row['comparison_id']
    a, b = [ident.rsplit('__', 1)[-1] for ident in row['case_ids']]
    left, right = receipts[a], receipts[b]
    compare(kind, left, right)
    stale = deepcopy(right)
    stale['fixture_manifest']['rider_motion.jsonl'] = '0' * 64
    try:
        compare(kind, left, stale)
    except ValueError as error:
        if 'fixed original changed: rider_motion.jsonl' not in str(error):
            raise
    else:
        raise AssertionError(kind + ' accepted a changed fixed original')
    results.append({'comparison_id': kind, 'cases': [a, b], 'fixed_originals': list(COMMON),
                    'deliberate_difference_checked': True, 'stale_fixed_original_rejected': True,
                    'physical_effect_verified': False, 'legal_judgment_claimed': False})

output = {'format': 'worker-rider-comparison-cpu-audit', 'comparisons': results,
          'physical_effect_verified': False, 'legal_judgment_claimed': False}
(ROOT / 'comparison-audit-j.json').write_text(json.dumps(output, indent=2) + '\n')
print('Seven controlled comparisons and seven stale-fixed-original negatives pass')
