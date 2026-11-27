"""Check source-backed Native device assets before selecting electric alternatives."""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = ROOT / 'runtime/python/carla_sgg/actors.py'
REQUIRED = ('electric_bicycle', 'electric_scooter')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_taxonomy():
    module = ast.parse(TAXONOMY.read_text())
    maps = {}
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('base_type_map', 'special_type_map'):
                    maps[target.id] = ast.literal_eval(node.value)
    if set(maps) != {'base_type_map', 'special_type_map'}:
        raise ValueError('Pinned CARLA actor taxonomy unavailable')
    return maps


def validate_supplied_asset(entry):
    if (entry.get('device_class') not in REQUIRED or
            not entry.get('blueprint_id') or
            not entry.get('native_asset_source') or
            not entry.get('native_asset_sha256') or
            not entry.get('legal_class_source') or
            not entry.get('legal_class_sha256') or
            not entry.get('original_class_review_required')):
        raise ValueError('Exact electric device asset source/class contract missing')
    if entry['blueprint_id'] in ('vehicle.bh.crossbike', 'vehicle.diamondback.century',
                                 'vehicle.gazelle.omafiets', 'vehicle.vespa.zx125'):
        raise ValueError('Ordinary bicycle or gasoline Vespa cannot be relabeled electric')
    if not re.fullmatch(r'vehicle\.[a-zA-Z0-9_.-]+', entry['blueprint_id']):
        raise ValueError('Exact Native vehicle blueprint ID required')
    for prefix in ('native_asset', 'legal_class', 'device_type', 'motor_power'):
        path = Path(entry[prefix + '_source'])
        digest = entry[prefix + '_sha256']
        if not path.is_file() or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Readable source and SHA-256 required for ' + prefix)
        if sha(path) != digest:
            raise ValueError('Source SHA-256 mismatch for ' + prefix)
    return entry['device_class']


def audit(inventory=None):
    maps = pinned_taxonomy()
    known = {name: kind for name, kind in maps['base_type_map'].items()
             if name.startswith('vehicle.')}
    electric = {name for name, kind in maps['special_type_map'].items()
                if kind == 'electric'}
    supplied = [] if inventory is None else json.loads(Path(inventory).read_text())['assets']
    classes = [validate_supplied_asset(entry) for entry in supplied]
    if len(classes) != len(set(classes)):
        raise ValueError('Ambiguous duplicate electric device class')
    blueprints = [entry['blueprint_id'] for entry in supplied]
    if len(blueprints) != len(set(blueprints)):
        raise ValueError('One Native blueprint cannot establish both electric device classes')
    return {'format': 'c230266-electric-device-asset-preflight-v1',
            'runtime_taxonomy_sha256': sha(TAXONOMY),
            'pinned_bicycle_blueprints': sorted(name for name, kind in known.items()
                                                if kind == 'bicycle'),
            'pinned_electric_blueprints': sorted(electric),
            'source_bound_electric_device_classes': sorted(classes),
            'missing_device_classes': sorted(set(REQUIRED) - set(classes)),
            'ready_for_exact_electric_cases': set(REQUIRED) <= set(classes),
            'physical_and_legal_class_verified': False}


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work') as folder:
        source = Path(folder)/'native-asset.uasset'
        law = Path(folder)/'class-source.txt'
        source.write_bytes(b'diagnostic only')
        law.write_text('diagnostic only')
        candidate = {'device_class': 'electric_bicycle',
                     'blueprint_id': 'vehicle.custom.verified_ebike',
                     'native_asset_source': str(source),
                     'native_asset_sha256': sha(source),
                     'legal_class_source': str(law),
                     'legal_class_sha256': sha(law),
                     'device_type_source': str(law),
                     'device_type_sha256': sha(law),
                     'motor_power_source': str(law),
                     'motor_power_sha256': sha(law),
                     'original_class_review_required': True}
        if validate_supplied_asset(candidate) != 'electric_bicycle':
            raise AssertionError('Exact electric bicycle asset contract rejected')
        for modified in ({**candidate, 'blueprint_id': 'vehicle.diamondback.century'},
                         {**candidate, 'blueprint_id': 'vehicle.vespa.zx125'},
                         {**candidate, 'native_asset_sha256': '0' * 64},
                         {**candidate, 'legal_class_source': 'not-a-real-source'}):
            try:
                validate_supplied_asset(modified)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid electric device evidence accepted')
    print(json.dumps({'selftest': 'passed', 'invalid_evidence_rejections': 4}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        selftest()
        raise SystemExit(0)
    result = audit(args.inventory)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
