"""Audit source-bound interior clearance sweep without an endangerment label."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.package_compatibility import check_receipts


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def audit(negative=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    check_receipts(ROOT, HERE, manifest)
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    spec = next(s for s in proposal['sweep_specs'] if s['status'] == 'complete')
    cases = {c['case_id']: c for c in proposal['cases'] if c.get('sweep_id') == spec['sweep_id']}
    entries = {e['case_id']: e for e in manifest['cases'] if e['case_id'] in cases}
    if set(entries) != set(spec['selection_order']) or spec['planned_case_count'] != 3:
        raise ValueError('Frozen three-point clearance sweep incomplete')
    fixed = None
    points = []
    for case_id in spec['selection_order']:
        case = cases[case_id]; entry = entries[case_id]
        config = next(f['content'] for f in json.loads((HERE / entry['construction']).read_text())['files']
                      if f['path'] == 'config.json')
        config = json.loads(config)
        requested = case['sweep_point']['outside_edge_m']
        if negative and case_id == spec['selection_order'][-1]:
            requested += 0.1
        if (config['outside_edge_m'] != requested or
                config['requested_speed_mps'] != 5 or config['exposed_kind'] != 'pedestrian' or
                config['duration_s'] != 8 or config['frames'] != 160):
            raise ValueError('Sweep authored placement or fixed construction differs')
        receipt_path = HERE / entry['compatibility']['receipt']
        if sha(receipt_path) != entry['compatibility']['sha256']:
            raise ValueError('Sweep source receipt changed')
        receipt = json.loads(receipt_path.read_text())
        if not receipt['passed'] or receipt['candidate_id'] != 'primary':
            raise ValueError('Sweep primary source compatibility missing')
        measurement = receipt['measurement_examples']['person_or_property_exposure']
        rows = measurement['value']['observations']
        if len(rows) != 9 or any(row['exposed_kind'] != 'pedestrian' or
                                 row['contact'] is not False for row in rows):
            raise ValueError('Original pedestrian exposure observations differ')
        sources = measurement['sources']
        invariant = {'trace': sources['trace.jsonl'],
                     'frame_map': sources['video_frames.jsonl'],
                     'road': receipt['fixture_manifest']['road.xodr'],
                     'camera_sources': {name: receipt['fixture_manifest'][name + '.mkv']
                                        for name in ('overview', 'approach',
                                                     'reference_corner', 'driver_reference')}}
        if fixed is None:
            fixed = invariant
        elif invariant != fixed:
            raise ValueError('Sweep changed fixed scene or original camera sources')
        points.append({'case_id': case_id, 'outside_edge_m_authored': requested,
                       'minimum_exposure_gap_m_original': measurement['value']['minimum_surface_gap_m'],
                       'original_body_sha256': sources['exposed_actor_footprints.jsonl']})
    gaps = [point['minimum_exposure_gap_m_original'] for point in sorted(
        points, key=lambda p: p['outside_edge_m_authored'])]
    if not all(a < b for a, b in zip(gaps, gaps[1:])):
        raise ValueError('Diagnostic original body clearance did not increase with placement')
    return {'format': 'worker-exposure-clearance-sweep-audit', 'passed': True,
            'scope': 'synthetic source-bound comparison only',
            'sweep_spec_version': spec['spec_version'], 'points': points,
            'fixed_source_hashes': fixed, 'physical_acceptance_claimed': False,
            'legal_endangerment_judgment': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.negative), indent=2))
