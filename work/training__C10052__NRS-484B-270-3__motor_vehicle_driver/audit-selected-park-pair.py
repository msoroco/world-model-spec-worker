"""Compare exact selected parking controls over fixed synthetic poses."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAMES = ('probe_park_released', 'probe_park_held')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(negative=False):
    manifest = json.loads((ROOT/'execution-manifest.json').read_text())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    comparison = next(row for row in plan['comparisons']
                      if row['comparison_id'] == ROOT.name+'__comparison_park_act')
    ids = [ROOT.name+'__'+name for name in NAMES]
    if comparison['case_ids'] != ids:
        raise ValueError('Selected parking comparison identity changed')
    observations, poses, controls = [], [], []
    for name, case in zip(NAMES, ids):
        here = ROOT/('selected-park-'+name)
        receipt_path = here/'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        if (receipt.get('passed') is not True or receipt.get('case_id') != case
                or receipt.get('construction_sha256') != entry['construction_sha256']
                or receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected parking receipt changed: '+name)
        source = here/'source/native_samples.jsonl'
        control = here/'source/native_controls.jsonl'
        poses.append([json.loads(line) for line in source.read_text().splitlines()])
        controls.append([json.loads(line) for line in control.read_text().splitlines()])
        value = receipt['measurement_examples']['parking_control_observation']['value']
        observations.append({'case_id': case, 'source_sha256': sha(source),
                             'control_sha256': sha(control),
                             'receipt_sha256': sha(receipt_path), 'value': value})
    if len(poses[0]) != 600 or poses[0] != poses[1]:
        raise ValueError('Parking pose fixed condition changed')
    if len(controls[0]) != 600 or len(controls[1]) != 600:
        raise ValueError('Parking controls incomplete')
    for released, held in zip(*controls):
        if any(released[key] != held[key] for key in
               ('native_frame', 'time_s', 'throttle', 'brake', 'control_source')):
            raise ValueError('Parking control fixed condition changed')
    if negative:
        observations[1]['value']['park_control_candidate'] = False
    released, held = (item['value'] for item in observations)
    if (released['park_control_candidate'] is not False
            or held['park_control_candidate'] is not True
            or held['held_duration_s'] < 2
            or held['max_held_facility_overlap_m2'] < 9):
        raise ValueError('Selected parking act contrast absent')
    proof = {'format': 'c10052-selected-park-comparison-cpu-v1',
             'comparison_id': comparison['comparison_id'], 'cases': observations,
             'fixed_pose_and_control_timing_verified': True,
             'deliberate_difference': 'synthetic retained hand brake control',
             'source_bound_cpu_passed': True, 'diagnostic_only': True,
             'original_native_observed': False, 'legal_verdict_claimed': False}
    if not negative:
        (ROOT/'selected-park-pair-comparison.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative), indent=2))
