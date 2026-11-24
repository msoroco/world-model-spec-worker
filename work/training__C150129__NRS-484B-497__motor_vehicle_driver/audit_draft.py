"""Independently compare exact permission-device drafts and pinned offline logs."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]
MAPPING = {'witness_1': True, 'witness_2': False,
           'exception_1_1': False, 'exception_1_2': True}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def audit(offline_root):
    manifest_path = CASE / 'draft-permission-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assignment = ROOT / 'inputs' / CASE.name / 'assignment.json'
    plan = CASE / 'case-plan.json'
    require(manifest['assignment_id'] == CASE.name
            and manifest['input_sha256'] == sha(assignment)
            and manifest['case_plan_sha256'] == sha(plan)
            and len(manifest['cases']) == 4, 'exact manifest/source binding differs')
    facts = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(CASE.name + '__')
        require(suffix in MAPPING, 'unexpected case')
        construction_path = CASE / entry['construction']
        require(sha(construction_path) == entry['construction_sha256'],
                'construction hash differs')
        construction = json.loads(construction_path.read_text())
        files = {row['path']: row['content'] for row in construction['files']}
        config = json.loads(files['config.json'])
        require(construction['case_id'] == config['case_id'] == entry['case_id']
                and config['permission_device_requested'] is MAPPING[suffix]
                and config['parking_side'] == 'left'
                and config['assignment_sha256'] == sha(assignment)
                and config['case_plan_sha256'] == sha(plan)
                and config['duration_s'] == 30 and config['rate_hz'] == 20
                and [camera['name'] for camera in config['cameras']] ==
                ['overview', 'sign_approach', 'sign_face', 'parking_side']
                and all(camera['width'] == 1280 and camera['height'] == 720
                        for camera in config['cameras']),
                'case permission/capture invariant differs')
        folder = offline_root / ('final-offline-' + suffix)
        selected = json.loads((folder / 'candidate-selection.json').read_text())
        require(selected['case_id'] == entry['case_id']
                and selected['construction_sha256'] == entry['construction_sha256']
                and selected['manifest_sha256'] == sha(manifest_path),
                'pinned offline selection differs')
        log = (folder / 'offline.log').read_text()
        require('Ran 2 tests' in log and 'OK' in log,
                'pinned offline native tests did not pass')
        facts.append({'case_id': entry['case_id'],
                      'permission_device_requested': MAPPING[suffix],
                      'construction_sha256': entry['construction_sha256'],
                      'offline_log_sha256': sha(folder / 'offline.log')})
    require({row['case_id'] for row in facts} ==
            {CASE.name + '__' + suffix for suffix in MAPPING},
            'case coverage differs')
    for first, second in (('witness_1', 'witness_2'),
                          ('exception_1_1', 'exception_1_2')):
        a, b = (next(row for row in facts if row['case_id'].endswith('__' + suffix))
                for suffix in (first, second))
        require(a['permission_device_requested'] != b['permission_device_requested'],
                'comparison did not vary permission device')
    result = {'format': 'nrs-484b-497-draft-independent-audit-v1',
              'assignment_id': CASE.name, 'manifest_sha256': sha(manifest_path),
              'input_sha256': sha(assignment), 'case_plan_sha256': sha(plan),
              'facts': facts, 'offline_cases_passed': 4,
              'physical_completion_verified': False, 'delivery_ready': False}
    destination = CASE / 'draft-permission-audit.json'
    destination.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline-root', type=Path, required=True)
    args = parser.parse_args()
    destination = audit(args.offline_root)
    print(json.dumps({'audit_sha256': sha(destination), 'cases': 4}))
