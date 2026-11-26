"""Source audit for the unselected LVMC 11.27.010(B)(3) alternative.

This checks original evidence bindings. It does not decide a legal outcome or
turn a conventional vehicle into an eligible mobility device.
"""
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(root, packet):
    """Validate separate device-design, user-use and actor records.

    The packet is an acquisition request until all three original records are
    supplied. The caller must still review their meaning and physical pixels.
    """
    root = Path(root).resolve()
    if packet.get('source_kind') != 'original_native':
        raise ValueError('Original Native mobility source required')
    records = packet.get('records')
    if not isinstance(records, dict) or set(records) != {
            'device_design', 'impaired_person_use', 'operator_binding'}:
        raise ValueError('Separate mobility source records required')
    bound = {}
    for name, ref in records.items():
        relative = ref.get('path')
        expected = ref.get('sha256')
        if not isinstance(relative, str) or not relative or not isinstance(expected, str):
            raise ValueError('Missing mobility source reference: ' + name)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Missing original mobility source: ' + name)
        if digest(path) != expected:
            raise ValueError('Mobility source hash mismatch: ' + name)
        record = json.loads(path.read_text())
        if record.get('source_kind') != 'original_native':
            raise ValueError('Non-original mobility record: ' + name)
        bound[name] = record
    device = bound['device_design']
    user = bound['impaired_person_use']
    operator = bound['operator_binding']
    actor_id = packet.get('subject_actor_id')
    if not isinstance(actor_id, int) or actor_id <= 0:
        raise ValueError('Original subject actor ID required')
    if any(row.get('subject_actor_id') != actor_id for row in bound.values()):
        raise ValueError('Mobility records bind different subject actors')
    if device.get('device_class') not in ('motorized_wheelchair', 'other_mobility_device'):
        raise ValueError('Mobility device class not established')
    if device.get('designed_for_mobility_impaired_person') is not True:
        raise ValueError('Mobility device design evidence absent')
    if user.get('mobility_impaired_person') is not True or user.get('device_in_use') is not True:
        raise ValueError('Impaired person use evidence absent')
    if user.get('person_id') != operator.get('person_id') or operator.get('operating_device') is not True:
        raise ValueError('Mobility operator binding absent')
    if device.get('blueprint_id') != operator.get('blueprint_id'):
        raise ValueError('Mobility blueprint identity differs')
    if packet.get('frozen_actor') != 'motor_vehicle_driver':
        raise ValueError('Frozen actor identity changed')
    return {
        'source_bound': True,
        'subject_actor_id': actor_id,
        'device_class': device['device_class'],
        'original_blueprint_id': device['blueprint_id'],
        'operator_person_id': user['person_id'],
        'source_hashes': {name: records[name]['sha256'] for name in records},
        'actor_eligibility_reviewed': False,
        'physical_pixels_reviewed': False,
        'legal_outcome_claimed': False,
    }
