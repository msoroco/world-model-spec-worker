"""Independent CPU audit of present versus absent entrance-device constructions."""
import hashlib
import json
from pathlib import Path

from device_branch import build_presence_pair, validate_device_pair

PRESENT = 'stop_ego_left_near_time'
ABSENT = 'stop_ego_left_near_time_no_device'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(root, name):
    return json.loads((root / name).read_text())


def audit(root):
    root = Path(root)
    names = {
        PRESENT: ('site.json', 'construction.json',
                  'first-camera-plan-supported-compatibility.json',
                  'first-camera-plan-supported-analysis.log',
                  'first-camera-plan-supported-negative.log',
                  'first-camera-plan-supported-saved.json'),
        ABSENT: ('absent-site.json', 'absent-construction.json',
                 'stop_no_device-primary-compatibility.json',
                 'stop_no_device-primary-analysis.log',
                 'stop_no_device-primary-negative.log',
                 'stop_no_device-primary-saved.json')}
    scenes, receipts = {}, {}
    for suffix, (site_name, construction_name, receipt_name, analysis_name,
                 negative_name, saved_name) in names.items():
        case = root.name + '__' + suffix
        scene = _read(root, site_name)
        construction = _read(root, construction_name)
        receipt = _read(root, receipt_name)
        saved = _read(root, saved_name)
        if (construction['case_id'] != case or receipt['case_id'] != case or
                saved['case_id'] != case):
            raise ValueError('Device pair case identity differs')
        if (receipt.get('passed') is not True or
                receipt.get('construction_sha256') != _sha(root / construction_name) or
                receipt.get('fixture_manifest', {}).get('site-source.json') != _sha(root / site_name)):
            raise ValueError('Device pair construction or site binding differs')
        if (receipt.get('log_sha256') != _sha(root / analysis_name) or
                receipt.get('negative_log_sha256') != _sha(root / negative_name) or
                receipt.get('negative_removed') != 'controller_history.jsonl' or
                'negative_case_source' not in receipt.get('checks', [])):
            raise ValueError('Device pair positive/negative compatibility proof changed')
        if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
                saved.get('native_revision', {}).get('construction_sha256') !=
                receipt['construction_sha256'] or
                saved.get('originals_preserved') is not True or
                saved.get('physical_acceptance_claimed') is not False or
                saved.get('legal_acceptance_claimed') is not False):
            raise ValueError('Device pair saved-source proof changed')
        scenes[suffix], receipts[suffix] = scene, receipt
    present, absent = scenes[PRESENT], scenes[ABSENT]
    if present['stop_sign']['native_id'] != 17 or absent.get('stop_sign') is not None:
        raise ValueError('Device presence contrast differs from source packets')
    if any(present.get(key) != absent.get(key) for key in
           ('native_map_name', 'intersection_id', 'crossing_polygon_xy_m',
            'same_statutory_crossing', 'approach_relation', 'approaches',
            'camera_poses', 'ego_stop_line_xy_m')):
        raise ValueError('Device pair changed a fixed crossing or participant condition')
    for role in ('sign_governance_source', 'sign_face_video_source'):
        path = root / ('absent-review/' + role + '.json')
        if (absent['source_documents'][role]['sha256'] != _sha(path) or
                _read(root, 'absent-review/' + role + '.json')['reviewed_site_fields']['stop_sign'] is not None):
            raise ValueError('Absent-device source document changed')
    contract_present, contract_absent = build_presence_pair(present)
    comparison = validate_device_pair(contract_present, contract_absent)
    actual = receipts[ABSENT]['measurement_examples']['device_qualification_context']['value']
    if actual.get('entrance_device_presence') != 'absent' or actual.get('native_stop_sign_id') is not None:
        raise ValueError('Absent-device source measurement differs')
    if receipts[PRESENT]['runtime_manifest_sha256'] != receipts[ABSENT]['runtime_manifest_sha256']:
        raise ValueError('Device pair uses different runtime revisions')
    return {'format': 'worker-c125745-device-comparison-cpu-audit',
            'case_ids': [receipts[PRESENT]['case_id'], receipts[ABSENT]['case_id']],
            'comparison': comparison,
            'construction_sha256': {key: receipts[key]['construction_sha256'] for key in names},
            'fixture_sha256': {key: receipts[key]['fixture_sha256'] for key in names},
            'recorded_only_passed': True,
            'official_device_judgment': 'unresolved',
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    (root / 'device-delivery-comparison.json').write_text(json.dumps(audit(root), indent=2) + '\n')
