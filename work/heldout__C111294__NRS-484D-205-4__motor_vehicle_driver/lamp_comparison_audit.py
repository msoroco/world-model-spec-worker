"""Independent saved-source comparison of exact C111294 cases."""
from hashlib import sha256
import json
from pathlib import Path

from lamp_finalizer import analyze


PAIRS = {
    'optional_equipment': ('no_backup_lamp_installed', 'forward_backup_lamp_off'),
    'forward_illumination': ('forward_backup_lamp_off', 'forward_backup_lamp_on'),
}
FIXED = ('law_id', 'cell_id', 'actor', 'ego_blueprint_id',
         'other_blueprint_id', 'approach_m', 'exit_m', 'ego_speed_mps',
         'other_speed_mps', 'rate_hz', 'duration_s', 'frames', 'cameras')


def _read(root, name):
    path = Path(root)/name
    return json.loads(path.read_text())


def audit(comparison_id, first_attempt, second_attempt):
    if comparison_id not in PAIRS:
        raise ValueError('Unknown exact comparison')
    expected = PAIRS[comparison_id]
    first, second = [Path(p) for p in (first_attempt, second_attempt)]
    configs = [_read(p, 'config.json') for p in (first, second)]
    if tuple(c['case_branch'] for c in configs) != expected:
        raise ValueError('Comparison exact-case identities differ')
    reports = [analyze(p, write_channels=False) for p in (first, second)]
    for key in FIXED:
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError('Fixed construction condition differs: '+key)
    contexts = [_read(p, 'intersection_context.json') for p in (first, second)]
    if contexts[0] != contexts[1]:
        raise ValueError('Fixed intersection and other-vehicle context differs')
    equipment = [_read(p, 'equipment.json') for p in (first, second)]
    values = [r['measurements']['backup_lamp_forward']['value'] for r in reports]
    if comparison_id == 'optional_equipment':
        if (len(equipment[0]['installed_backup_lamps']),
                len(equipment[1]['installed_backup_lamps'])) != (0, 1):
            raise ValueError('Optional-equipment difference unobserved')
        if any(v['forward_with_native_lamp_bit_frames'] for v in values):
            raise ValueError('Lamp state changed in optional-equipment comparison')
    else:
        if len(equipment[0]['installed_backup_lamps']) != len(equipment[1]['installed_backup_lamps']):
            raise ValueError('Fixed installed backup-lamp inventory differs')
        if (values[0]['forward_with_native_lamp_bit_frames'] or
                not values[1]['forward_with_native_lamp_bit_frames']):
            raise ValueError('Forward lamp-state difference unobserved')
    # Require motion in both attempts without asserting exact physical equality.
    if not all(v['forward_frames'] for v in values):
        raise ValueError('Measured forward motion missing')
    return {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
            'case_ids': [r['case_id'] for r in reports],
            'source_hashes': [{name: sha256((p/name).read_bytes()).hexdigest()
                               for name in ('config.json', 'intersection_context.json',
                                            'equipment.json', 'motion.jsonl',
                                            'other_vehicle.jsonl', 'video_frames.jsonl')}
                              for p in (first, second)],
            'fixed_conditions_checked': True,
            'deliberate_difference_checked': True,
            'actual_pixels_reviewed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}
