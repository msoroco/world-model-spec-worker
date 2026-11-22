"""Independent saved-evidence comparison checks for the two U-turn cases.

Inputs must be measurements from original synchronized Native capture. Intended
configuration and synthetic fixtures alone cannot satisfy this audit.
"""
import argparse
import importlib.util
import json
from pathlib import Path

_delivery_spec=importlib.util.spec_from_file_location(
    'c10808_pair_delivery_audit',Path(__file__).with_name('delivery_audit.py'))
_delivery=importlib.util.module_from_spec(_delivery_spec)
_delivery_spec.loader.exec_module(_delivery)
audit_delivery,read,sha=_delivery.audit,_delivery.read,_delivery.sha

FIXED = ('law_id', 'cell_id', 'operator_id', 'bicycle_id', 'sign_id',
         'sign_authorization_source_sha256', 'alley_geometry_sha256',
         'camera_contract_sha256', 'duration_s')


def require_measured(record, name):
    value = record.get(name)
    if value is None or record.get('sources', {}).get(name, {}).get('kind') != 'original_native':
        raise ValueError('missing original Native evidence: ' + name)
    source = record['sources'][name]
    if not source.get('path') or not source.get('sha256'):
        raise ValueError('unbound original Native source: ' + name)
    return value


def audit(dismounted, mounted):
    for field in FIXED:
        if dismounted.get(field) is None or mounted.get(field) is None:
            raise ValueError('missing fixed condition: ' + field)
        if dismounted[field] != mounted[field]:
            raise ValueError('fixed condition differs: ' + field)
    for label, record in (('dismounted', dismounted), ('mounted', mounted)):
        sign = require_measured(record, 'observed_sign')
        if sign.get('message') != 'NO U TURN' or not sign.get('erected'):
            raise ValueError(label + ': governing sign not observed')
        require_measured(record, 'turn_start_s')
        require_measured(record, 'turn_complete_s')
        if record['turn_complete_s'] <= record['turn_start_s']:
            raise ValueError(label + ': reversal not completed')
    t_dismount = require_measured(dismounted, 'dismount_time_s')
    afoot = require_measured(dismounted, 'afoot_body_samples')
    if not afoot or t_dismount >= dismounted['turn_start_s']:
        raise ValueError('dismount not observed before reversal')
    if min(sample['time_s'] for sample in afoot) > dismounted['turn_start_s']:
        raise ValueError('afoot body state absent at reversal start')
    mounted_states = require_measured(mounted, 'mounted_body_samples')
    if not mounted_states or max(sample['time_s'] for sample in mounted_states) < mounted['turn_start_s']:
        raise ValueError('mounted body state absent at reversal start')
    if mounted.get('dismount_time_s') is not None:
        raise ValueError('mounted comparison contains a dismount')
    return {'comparison_id': 'uturn_dismount_exception', 'passed': True,
            'fixed_conditions': list(FIXED), 'deliberate_difference': 'observed dismount before reversal'}


def audit_sealed_pair(dismount_attempt, dismount_processing, dismount_decode,
                      mounted_attempt, mounted_processing, mounted_decode,
                      media_verify=None):
    """Compare two independently accepted, sealed Native attempts."""
    prefix='testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator__'
    attempts=((Path(dismount_attempt),dismount_processing,dismount_decode,
               prefix+'dismount_before_uturn'),
              (Path(mounted_attempt),mounted_processing,mounted_decode,
               prefix+'mounted_uturn'))
    receipts=[]
    for attempt,processing,decode,case_id in attempts:
        receipts.append(audit_delivery(attempt,processing,decode,case_id,
                                       media_verify=media_verify))
    left,right=(item[0] for item in attempts)
    left_sign,right_sign=(read(path/'sign-inventory.json') for path in (left,right))
    left_config,right_config=(read(path/'config.json') for path in (left,right))
    fixed={
        'road.xodr':(sha(left/'road.xodr'),sha(right/'road.xodr')),
        'sign_authorization_source':(receipts[0]['sign_source_sha256'],receipts[1]['sign_source_sha256']),
        'fixed_scene':(left_sign.get('fixed_scene_sha256'),right_sign.get('fixed_scene_sha256')),
        'camera_contract':(left_sign.get('camera_contract_sha256'),right_sign.get('camera_contract_sha256')),
        'sign_blueprint':(left_sign.get('sign_blueprint'),right_sign.get('sign_blueprint')),
        'bicycle_blueprint':(left_sign.get('bicycle_blueprint'),right_sign.get('bicycle_blueprint')),
        'operator_blueprint':(left_sign.get('operator_blueprint'),right_sign.get('operator_blueprint')),
        'map_context':(left_sign.get('map_context'),right_sign.get('map_context')),
        'duration_s':(left_config.get('duration_s'),right_config.get('duration_s')),
        'rate_hz':(left_config.get('rate_hz'),right_config.get('rate_hz')),
        'frame_count':(receipts[0]['frame_count'],receipts[1]['frame_count'])}
    for name,(a,b) in fixed.items():
        if a is None or b is None or a!=b:
            raise ValueError('sealed comparison fixed condition missing or differs: '+name)
    if (receipts[0]['dismounted_before_turn'] is not True or
            receipts[1]['dismounted_before_turn'] is not False):
        raise ValueError('observed dismount difference missing')
    return {'format':'worker-sealed-comparison','comparison_id':'uturn_dismount_exception',
            'passed':True,'case_ids':[item[3] for item in attempts],
            'capture_seal_sha256':[sha(path/'capture-seal.json') for path in (left,right)],
            'native_result_sha256':[r['native_result_sha256'] for r in receipts],
            'fixed_conditions':list(fixed),
            'deliberate_difference':'source-observed dismount before U-turn',
            'legal_verdict':None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dismounted')
    parser.add_argument('mounted')
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.dismounted).read_text()),
                           json.loads(Path(args.mounted).read_text())), indent=2))


if __name__ == '__main__':
    main()
