"""Audit selected CPU diagnostic proof bindings without original acceptance."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(relative, digest=None):
    path = HERE / relative
    require(path.is_file() and not path.is_symlink(), 'selected proof missing: ' + relative)
    if digest is not None:
        require(sha(path) == digest, 'selected proof hash changed: ' + relative)
    return path


def audit():
    manifest = json.loads(bound('execution-manifest.json').read_text())
    plan = json.loads(bound('case-plan.json').read_text())
    expected = {case['case_id'] for case in plan['cases']}
    require(manifest.get('assignment_id') == HERE.name and
            {entry['case_id'] for entry in manifest['cases']} == expected and
            len(expected) == len(manifest['cases']) == 10,
            'selected exact case coverage changed')
    reports = {}
    for entry in manifest['cases']:
        case_id = entry['case_id']
        name = case_id.removeprefix(PREFIX)
        construction = json.loads(bound(entry['construction'], entry['construction_sha256']).read_text())
        require(construction.get('case_id') == case_id and construction.get('diagnostic_only') is True,
                'selected diagnostic construction changed')
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        require(config.get('selected_case_id') == case_id and config.get('rate_hz') == 20
                and config.get('duration_s') == 45, 'selected capture contract changed')
        scene = json.loads(next(item['content'] for item in construction['files']
                                if item['path'] == 'scene.json'))
        require(scene.get('case_id') == case_id and scene.get('source_kind') == 'synthetic_diagnostic_fixture'
                and scene.get('accepted_original_source') is False, 'diagnostic provenance changed')
        offline = entry['offline']
        require(offline.get('exit_code') == 0 and
                offline.get('construction_sha256') == entry['construction_sha256'],
                'selected offline result changed')
        bound(offline['log'], offline['log_sha256'])
        compatible = entry['compatibility']
        receipt = json.loads(bound(compatible['receipt'], compatible['sha256']).read_text())
        require(receipt.get('passed') is True and receipt.get('case_id') == case_id
                and receipt.get('construction_sha256') == entry['construction_sha256']
                and receipt.get('scope') == 'diagnostic software compatibility only'
                and 'negative_case_source' in receipt.get('checks', []),
                'selected compatibility proof changed')
        bound(compatible['log'], receipt['log_sha256'])
        bound(entry['negative']['log'], receipt['negative_log_sha256'])
        physical = entry['physical_preparation']
        physical_receipt = json.loads(bound(physical['receipt'], physical['sha256']).read_text())
        require(physical_receipt.get('case_id') == case_id and
                physical_receipt.get('construction_sha256') == entry['construction_sha256'] and
                physical_receipt.get('diagnostic_fixture') is True,
                'selected physical preparation changed')
        require([fixture['kind'] for fixture in physical_receipt['fixtures']] ==
                ['complete_motion', 'incomplete_motion', 'missing_evidence'],
                'selected physical three-state proof changed')
        for fixture in physical_receipt['fixtures']:
            bound(fixture['log'], fixture['log_sha256'])
            bound(fixture['result'], fixture['result_sha256'])
        lifecycle = physical_receipt['lifecycle']
        bound(lifecycle['log'], lifecycle['log_sha256'])
        saved = entry['post_capture']
        require(saved.get('recorded_only') is True and saved.get('test_exit_code') == 0,
                'recorded-only saved proof changed')
        bound(saved['test_log'], saved['test_log_sha256'])
        reports[case_id] = {'case_id': case_id, 'name': name,
                            'maneuver': config['case']['maneuver'],
                            'response': config['case']['response'],
                            'engineering': {key: config['case'].get(key) for key in
                                ('antecedent_pause_s', 'through_approach_speed_mps')},
                            'construction_sha256': entry['construction_sha256'],
                            'compatibility_receipt_sha256': compatible['sha256'],
                            'source_kind': 'synthetic_diagnostic_fixture',
                            'physical_acceptance': False, 'legal_status': 'unresolved'}
    comparisons = []
    for row in plan['comparisons']:
        ids = row['case_ids']
        require(len(ids) in (2, 3) and len(set(ids)) == len(ids) and set(ids) <= expected,
                'selected comparison members changed')
        values = [reports[case]['response'] for case in ids]
        if row['comparison_id'].startswith('engineering_antecedent_pause'):
            values = [reports[case]['engineering']['antecedent_pause_s'] for case in ids]
            require(len(set(values)) == 3, 'selected antecedent engineering grid collapsed')
        elif row['comparison_id'].startswith('engineering_precedence_speed'):
            values = [reports[case]['engineering']['through_approach_speed_mps'] for case in ids]
            require(len(set(values)) == 3, 'selected speed engineering grid collapsed')
        else:
            require(values == ['yield_request', 'continue_request'],
                    'selected through-driver response difference changed')
            require(len({reports[case]['maneuver'] for case in ids}) == 1,
                    'selected fixed entering maneuver changed')
        comparisons.append({'comparison_id': row['comparison_id'], 'case_ids': ids,
                            'declared_values': values, 'original_source_verified': False})
    return {'format': 'c179789-selected-diagnostic-audit-v1',
            'assignment_id': HERE.name, 'selected_cases': reports,
            'comparisons': comparisons, 'original_source_verified': False,
            'legal_status': 'unresolved', 'physical_acceptance': False}


if __name__ == '__main__':
    (HERE / 'selected-audit.json').write_text(json.dumps(audit(), indent=2) + '\n')
