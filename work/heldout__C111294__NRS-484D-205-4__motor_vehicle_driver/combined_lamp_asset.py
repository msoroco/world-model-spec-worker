"""Source-backed combined backup-lamp arrangement for a future exact case.

Native light bits cannot establish housing geometry. The operator must supply
an independently reviewed asset inspection for the selected vehicle blueprint.
"""
from hashlib import sha256
import json
from pathlib import Path


def validate_combined_inventory(path, blueprint_id):
    path = Path(path)
    raw = path.read_bytes()
    record = json.loads(raw)
    if (record.get('blueprint_id') != blueprint_id or
            record.get('inspection_method') not in ('asset_mesh_review', 'physical_asset_review') or
            not record.get('inspector') or
            record.get('inspection_status') != 'reviewed'):
        raise ValueError('Combined-lamp asset inspection is missing or unreviewed')
    backup = record.get('installed_backup_lamps')
    others = record.get('other_lamps')
    if not isinstance(backup, list) or not backup or not isinstance(others, list) or not others:
        raise ValueError('Combined arrangement needs backup and other lamp inventories')
    other_by_housing = {}
    for lamp in others:
        if (not isinstance(lamp, dict) or not lamp.get('housing_id') or
                not lamp.get('lamp_function') or not lamp.get('asset_source')):
            raise ValueError('Other lamp lacks inspected housing and function')
        other_by_housing.setdefault(lamp['housing_id'], []).append(lamp)
    for lamp in backup:
        if (not isinstance(lamp, dict) or not lamp.get('location') or
                not lamp.get('asset_source') or not lamp.get('housing_id') or
                lamp.get('arrangement') != 'combined' or
                not other_by_housing.get(lamp['housing_id'])):
            raise ValueError('Backup lamp is not source-linked to another function in one housing')
    return {'blueprint_id': blueprint_id, 'arrangement': 'combined',
            'installed_backup_lamp_count': len(backup),
            'shared_housing_ids': sorted({lamp['housing_id'] for lamp in backup}),
            'installed_backup_lamps': backup, 'other_lamps': others,
            'inspection_source_sha256': sha256(raw).hexdigest(),
            'inspection_method': record['inspection_method'],
            'inspector': record['inspector'],
            'physical_acceptance_claimed': False}


def construct_combined(world, carla, config, inventory_path):
    """Create the normal scene only after checking the actual chosen asset."""
    inspected = validate_combined_inventory(inventory_path, config['ego_blueprint_id'])
    if (config.get('installed_backup_lamp_count') != inspected['installed_backup_lamp_count'] or
            config.get('lamp_arrangement') != 'combined'):
        raise ValueError('Exact combined construction differs from inspected asset')
    from lamp_scene import construct
    scene = construct(world, carla, config, inventory_path)
    scene['equipment']['arrangement'] = 'combined'
    scene['equipment']['shared_housing_ids'] = inspected['shared_housing_ids']
    scene['equipment']['other_lamps'] = inspected['other_lamps']
    scene['equipment']['combined_inspection_sha256'] = inspected['inspection_source_sha256']
    return scene


def verify_combined_capture(equipment_path, blueprint_id):
    """Check the retained original equipment packet after Native capture."""
    packet = json.loads(Path(equipment_path).read_text())
    if (packet.get('blueprint_id') != blueprint_id or packet.get('arrangement') != 'combined'
            or not packet.get('combined_inspection_sha256')):
        raise ValueError('Original combined equipment identity missing')
    backups = packet.get('installed_backup_lamps')
    others = packet.get('other_lamps')
    if not isinstance(backups, list) or not backups or not isinstance(others, list) or not others:
        raise ValueError('Original combined equipment inventory incomplete')
    other_housings = {lamp.get('housing_id') for lamp in others if isinstance(lamp, dict)
                      and lamp.get('lamp_function') and lamp.get('asset_source')}
    if any(not isinstance(lamp, dict) or lamp.get('arrangement') != 'combined'
           or not lamp.get('asset_source') or lamp.get('housing_id') not in other_housings
           for lamp in backups):
        raise ValueError('Original backup/other lamp shared housing differs')
    shared = sorted({lamp['housing_id'] for lamp in backups})
    if shared != packet.get('shared_housing_ids'):
        raise ValueError('Original backup/other lamp shared housing differs')
    return {'arrangement': 'combined', 'shared_housing_ids': shared,
            'equipment_source_sha256': sha256(Path(equipment_path).read_bytes()).hexdigest(),
            'inspection_source_sha256': packet['combined_inspection_sha256'],
            'actual_pixel_emission_observed': None, 'physical_acceptance_claimed': False}
