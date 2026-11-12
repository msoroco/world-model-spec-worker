"""Independent combined-housing source check around the lamp delivery audit."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from combined_lamp_asset import verify_combined_capture
from delivery_audit import audit as audit_lamp


def audit(case, attempt, diagnostic_fixture=False):
    root = Path(attempt)
    if not case.endswith('__forward_combined_backup_lamp_off'):
        raise ValueError('Wrong exact combined-housing case')
    baseline = audit_lamp(case, root, diagnostic_fixture=diagnostic_fixture)
    config = json.loads((root / 'config.json').read_text())
    if config.get('lamp_arrangement') != 'combined':
        raise ValueError('Combined-housing config changed')
    packet = verify_combined_capture(root / 'equipment.json', config['ego_blueprint_id'])
    inspection = root / config['equipment_inventory']
    if not inspection.is_file() or not inspection.read_bytes():
        raise ValueError('Missing original combined asset inspection')
    source_hash = sha256(inspection.read_bytes()).hexdigest()
    if source_hash != packet['inspection_source_sha256']:
        raise ValueError('Combined asset inspection hash changed')
    baseline['combined_housing_source_sha256'] = source_hash
    baseline['combined_housing_ids'] = packet['shared_housing_ids']
    baseline['combined_housing_physical_reviewed'] = False
    return baseline


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    parser.add_argument('--remove-source', choices=('equipment.json', 'asset-inspection.json'))
    args = parser.parse_args()
    if args.remove_source:
        with TemporaryDirectory(prefix='combined-audit-negative-') as temp:
            target = Path(temp)
            for source in Path(args.attempt).iterdir():
                if source.name != args.remove_source:
                    (target / source.name).symlink_to(source.resolve())
            print(json.dumps(audit(args.case, target, args.diagnostic_fixture), indent=2))
    else:
        print(json.dumps(audit(args.case, args.attempt, args.diagnostic_fixture), indent=2))
