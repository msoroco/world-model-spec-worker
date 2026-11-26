"""Compare retained source-bound synthetic alley and straight route controls."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAMES = ('probe_c_alley_entry', 'probe_d_no_entry')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(negative=False):
    manifest = json.loads((ROOT/'execution-manifest.json').read_text())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    comparison = next(row for row in plan['comparisons']
                      if row['comparison_id'] == ROOT.name+'__comparison_entry_no_entry')
    ids = [ROOT.name+'__'+name for name in NAMES]
    if comparison['case_ids'] != ids:
        raise ValueError('Selected alley comparison identity changed')
    observations = []
    sources = []
    for name, case in zip(NAMES, ids):
        here = ROOT/('selected-entry-'+name)
        receipt_path = here/'compatibility.json'
        receipt = json.loads(receipt_path.read_text())
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        if (receipt.get('passed') is not True or receipt.get('case_id') != case
                or receipt.get('construction_sha256') != entry['construction_sha256']
                or receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected alley receipt changed: '+name)
        source = here/'source/native_samples.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if len(rows) != 600:
            raise ValueError('Selected alley source incomplete')
        sources.append(rows)
        key = ('alley_transition_observation' if name == NAMES[0]
               else 'moving_body_facility_entry')
        value = receipt['measurement_examples'][key]['value']
        observations.append({'case_id': case, 'receipt_sha256': sha(receipt_path),
                             'source_sha256': sha(source), 'value': value})
    for first, second in zip(*sources):
        if (first['native_frame'] != second['native_frame']
                or first['time_s'] != second['time_s']
                or first['native_center_xy_m'][0] != second['native_center_xy_m'][0]):
            raise ValueError('Alley comparison fixed frame/time/x route changed')
    alley = observations[0]['value']
    straight = observations[1]['value']
    if negative:
        alley['time_bounded_geometry_candidate'] = False
    if (alley['time_bounded_geometry_candidate'] is not True
            or alley['simultaneous_moving_overlap_frames'] <= 0
            or alley['facility_to_alley_gap_s'] is None
            or not 0 <= alley['facility_to_alley_gap_s'] <= 2
            or straight['moving_entry_measured'] is not False
            or straight['moving_occupied_frames'] != 0):
        raise ValueError('Selected alley versus straight-route contrast absent')
    proof = {'format': 'c10052-selected-entry-comparison-cpu-v1',
             'comparison_id': comparison['comparison_id'], 'cases': observations,
             'fixed_frame_time_x_route_verified': True,
             'deliberate_difference': 'synthetic ego lateral path at alley entrance',
             'source_bound_cpu_passed': True, 'diagnostic_only': True,
             'original_native_observed': False, 'legal_verdict_claimed': False}
    if not negative:
        (ROOT/'selected-entry-pair-comparison.json').write_text(
            json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.negative), indent=2))
