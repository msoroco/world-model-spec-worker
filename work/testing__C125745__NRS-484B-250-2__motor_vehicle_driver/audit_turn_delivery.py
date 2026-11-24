"""Independently audit the CPU left/straight turn-intent proof pair."""
import hashlib
import json
from pathlib import Path

from turn_branch import validate_turn_pair

LEFT = 'stop_opposite_left_turn'
STRAIGHT = 'stop_opposite_straight'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(root, name):
    return json.loads((root / name).read_text())


def audit(root):
    root = Path(root)
    names = {
        LEFT: ('fourth-site.json', 'fourth-construction.json',
               'stop_opposite_left_turn-primary-current-runtime-compatibility.json',
               'stop_opposite_left_turn-primary-current-runtime-analysis.log',
               'stop_opposite_left_turn-primary-current-runtime-negative.log',
               'fourth-primary-saved-v1.log'),
        STRAIGHT: ('straight-site.json', 'straight-construction.json',
                   'stop_opposite_straight-primary-compatibility.json',
                   'stop_opposite_straight-primary-analysis.log',
                   'stop_opposite_straight-primary-negative.log',
                   'stop_opposite_straight-primary-saved.json')}
    scenes, receipts, saved = {}, {}, {}
    for suffix, (site_name, construction_name, receipt_name, analysis_name,
                 negative_name, saved_name) in names.items():
        case = root.name + '__' + suffix
        site = _read(root, site_name)
        construction = _read(root, construction_name)
        receipt = _read(root, receipt_name)
        process = _read(root, saved_name)
        if construction['case_id'] != case or receipt['case_id'] != case or process['case_id'] != case:
            raise ValueError('Case identity differs across turn proof')
        if (receipt.get('passed') is not True or
                receipt.get('construction_sha256') != _sha(root / construction_name) or
                receipt.get('fixture_manifest', {}).get('site-source.json') != _sha(root / site_name)):
            raise ValueError('Turn fixture or construction source binding differs')
        if (receipt.get('log_sha256') != _sha(root / analysis_name) or
                receipt.get('negative_log_sha256') != _sha(root / negative_name) or
                receipt.get('negative_removed') != 'controller_history.jsonl' or
                'negative_case_source' not in receipt.get('checks', [])):
            raise ValueError('Turn positive/negative proof missing or changed')
        if (process.get('passed') is not True or process.get('recorded_only') is not True or
                process.get('native_revision', {}).get('construction_sha256') !=
                receipt['construction_sha256'] or
                process.get('originals_preserved') is not True or
                process.get('physical_acceptance_claimed') is not False or
                process.get('legal_acceptance_claimed') is not False):
            raise ValueError('Turn saved-source processing proof missing or changed')
        scenes[suffix], receipts[suffix], saved[suffix] = site, receipt, process
    comparison = validate_turn_pair(scenes[LEFT], scenes[STRAIGHT])
    if receipts[LEFT]['runtime_manifest_sha256'] != receipts[STRAIGHT]['runtime_manifest_sha256']:
        raise ValueError('Turn pair was checked against different runtime revisions')
    a = receipts[LEFT]['measurement_examples']['opposite_left_turn_context']['value']
    b = receipts[STRAIGHT]['measurement_examples']['opposite_left_turn_context']['value']
    if (a.get('opposite_approach') is not True or b.get('opposite_approach') is not True or
            b.get('other_left_turn_intended') is not False):
        raise ValueError('Turn intention measurement differs from selected branches')
    return {'format': 'worker-c125745-turn-comparison-cpu-audit',
            'case_ids': [receipts[LEFT]['case_id'], receipts[STRAIGHT]['case_id']],
            'comparison': comparison,
            'construction_sha256': {key: receipts[key]['construction_sha256'] for key in names},
            'fixture_sha256': {key: receipts[key]['fixture_sha256'] for key in names},
            'recorded_only_passed': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    (root / 'turn-delivery-comparison.json').write_text(json.dumps(audit(root), indent=2) + '\n')
