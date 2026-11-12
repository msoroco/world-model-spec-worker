"""Compare source-measured separate and combined backup-lamp housings."""

from hashlib import sha256
import json
from pathlib import Path

from backup_lamp_measurement import measure
from combined_lamp_asset import validate_combined_inventory, verify_combined_capture


FIXED_CONFIG = ('law_id', 'cell_id', 'actor', 'ego_blueprint_id',
                'other_blueprint_id', 'approach_m', 'exit_m', 'ego_speed_mps',
                'other_speed_mps', 'rate_hz', 'duration_s', 'frames', 'cameras',
                'command_backup_lamp_on', 'installed_backup_lamp_count')
FIXED_SOURCES = ('motion.jsonl', 'other_vehicle.jsonl', 'video_frames.jsonl',
                 'trace.jsonl', 'intersection_context.json')


def _read(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original comparison source: ' + name)
    return json.loads(path.read_text())


def audit(separate_attempt, combined_attempt):
    first, second = Path(separate_attempt), Path(combined_attempt)
    configs = [_read(root, 'config.json') for root in (first, second)]
    if [config.get('case_branch') for config in configs] != [
            'forward_backup_lamp_off', 'forward_combined_backup_lamp_off']:
        raise ValueError('Separate/combined exact-case identities differ')
    for key in FIXED_CONFIG:
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError('Fixed comparison construction differs: ' + key)
    sources = {}
    for name in FIXED_SOURCES:
        a, b = first / name, second / name
        if not a.is_file() or not b.is_file() or a.read_bytes() != b.read_bytes():
            raise ValueError('Fixed original comparison source differs: ' + name)
        sources[name] = sha256(a.read_bytes()).hexdigest()
    first_equipment = _read(first, 'equipment.json')
    second_equipment = _read(second, 'equipment.json')
    if len(first_equipment.get('installed_backup_lamps', [])) != 1 or (
            first_equipment.get('arrangement') == 'combined'):
        raise ValueError('Separate backup-lamp reference inventory differs')
    inventory = second / configs[1]['equipment_inventory']
    inspected = validate_combined_inventory(inventory, configs[1]['ego_blueprint_id'])
    measured = verify_combined_capture(second / 'equipment.json',
                                       configs[1]['ego_blueprint_id'])
    if measured['inspection_source_sha256'] != inspected['inspection_source_sha256']:
        raise ValueError('Combined inspection source hash differs')
    if measured['shared_housing_ids'] != inspected['shared_housing_ids']:
        raise ValueError('Combined housing difference unobserved')
    if [measure(root/'motion.jsonl', root/'equipment.json', root/'video_frames.jsonl')[
            'forward_with_native_lamp_bit_frames'] for root in (first, second)] != [[], []]:
        raise ValueError('Fixed forward lamp-off state differs')
    return {'format': 'worker-comparison-audit',
            'comparison_id': 'separate_vs_combined_housing',
            'case_ids': [config['selected_case_id'] for config in configs],
            'fixed_source_sha256': sources,
            'separate_equipment_sha256': sha256((first/'equipment.json').read_bytes()).hexdigest(),
            'combined_equipment_sha256': measured['equipment_source_sha256'],
            'combined_inspection_sha256': inspected['inspection_source_sha256'],
            'shared_housing_ids': measured['shared_housing_ids'],
            'fixed_conditions_checked': True, 'deliberate_difference_checked': True,
            'actual_pixels_reviewed': False, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}
