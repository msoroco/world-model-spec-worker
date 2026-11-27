"""Build conditional electric-device configs after exact asset evidence arrives.

The output is unselected planning material. It is never a proof of Native
spawnability, physical behavior, legal classification, or delivery readiness.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from device_asset_preflight import audit, validate_supplied_asset

HERE = Path(__file__).resolve().parent
REQUIRED = ('electric_bicycle', 'electric_scooter')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(inventory_path):
    inventory = json.loads(Path(inventory_path).read_text())
    assets = inventory.get('assets', [])
    preflight = audit(inventory_path)
    if not preflight['ready_for_exact_electric_cases']:
        raise ValueError('Both source-bound electric device classes required')
    by_class = {validate_supplied_asset(asset): asset for asset in assets}
    if set(by_class) != set(REQUIRED):
        raise ValueError('Exactly one source-bound asset per electric class required')
    plan = json.loads((HERE / 'electric-alternative-plan.json').read_text())
    baseline = json.loads((HERE / 'config.json').read_text())
    entries = []
    seen = set()
    for item in plan['cases']:
        case_id = item['case_id']
        device_class = item['device_class']
        if case_id in seen or device_class not in by_class:
            raise ValueError('Duplicate case or unsupported device class')
        seen.add(case_id)
        if not case_id.startswith(HERE.name + '__'):
            raise ValueError('Electric case belongs to another assignment')
        config = copy.deepcopy(baseline)
        asset = by_class[device_class]
        config.update({'case_id': case_id, 'selected_case_id': case_id,
                       'device_class': device_class,
                       'device_blueprint_filter': asset['blueprint_id'],
                       'source_bound_blueprint_id': asset['blueprint_id'],
                       'native_asset_source': asset['native_asset_source'],
                       'native_asset_sha256': asset['native_asset_sha256'],
                       'legal_class_source': asset['legal_class_source'],
                       'legal_class_sha256': asset['legal_class_sha256'],
                       'device_type_source': asset['device_type_source'],
                       'device_type_sha256': asset['device_type_sha256'],
                       'motor_power_source': asset['motor_power_source'],
                       'motor_power_sha256': asset['motor_power_sha256'],
                       'signal_frame': 80 if item['requested_signal'] else None,
                       'pause_window_frames': [80, 110] if item['requested_yield_pause'] else [0, 0],
                       'target_request': {'pause_requested': item['requested_yield_pause'],
                                          'signal_requested': item['requested_signal']},
                       'rider_speaker_alsa_device_env': 'C230266_SPEAKER_ALSA_DEVICE'
                       if item['requested_signal'] else None})
        entries.append({'case_id': case_id, 'device_class': device_class,
                        'config': config, 'status': 'conditional_unselected'})
    if len(entries) != 6 or {e['device_class'] for e in entries} != set(REQUIRED):
        raise ValueError('Six exact electric alternatives required')
    case_ids = [entry['case_id'] for entry in entries]
    for entry in entries:
        entry['config']['supported_case_ids'] = case_ids
    from sys import path as sys_path
    sys_path.insert(0, str(HERE / 'native'))
    from electric_runner import check
    for entry in entries:
        check(entry['config'])
    return {'format': 'c230266-conditional-electric-construction-v1',
            'assignment_id': HERE.name, 'status': 'conditional_unselected',
            'native_runner': 'native/electric_runner.py',
            'native_runner_sha256': sha(HERE / 'native/electric_runner.py'),
            'preflight': preflight, 'cases': entries,
            'physical_and_legal_class_verified': False,
            'delivery_ready': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.inventory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(result['cases']), 'status': result['status']}))


if __name__ == '__main__':
    main()
