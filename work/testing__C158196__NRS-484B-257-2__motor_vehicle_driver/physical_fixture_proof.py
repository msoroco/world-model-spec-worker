"""Build and assess original-source motion diagnostics without claiming Native capture."""

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
         'missing_evidence': 'unverified'}


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def write_rows(path, records):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in records))


def run(case_suffix, kind, output):
    if kind not in KINDS:
        raise ValueError('Unknown physical fixture outcome')
    if not case_suffix.replace('_', '').isalnum():
        raise ValueError('Invalid exact case suffix')
    construction_path = ROOT / 'cases' / (case_suffix + '-construction.json')
    if case_suffix == 'active_signal_controls':
        construction_path = ROOT / 'construction.json'
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    if not config['selected_case_id'].endswith('__' + case_suffix):
        raise ValueError('Construction case suffix mismatch')
    spec = json.loads((ROOT / 'cases' / (case_suffix + '-diagnostic-sources.json')).read_text())
    recipe = json.loads((ROOT / 'cases' / (case_suffix + '-fixture-recipe.json')).read_text())
    inventory = next(item for item in recipe['sources']
                     if item['path'] == 'entrance_inventory.json')
    source_path = REPO / inventory['source']
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != inventory['sha256']:
        raise ValueError('Entrance inventory source changed')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    (output / 'entrance_inventory.json').write_bytes(source_path.read_bytes())
    crossing = rows(spec['files']['crossing_history.jsonl'])
    trace = rows(spec['files']['trace.jsonl'])
    mapping = rows(spec['files']['video_frames.jsonl'])
    if kind == 'complete_motion':
        last = copy.deepcopy(crossing[-1])
        shift = 21.0
        last['ego_body_vertices_xy_m'] = [[point[0] + shift, point[1]]
                                           for point in last['ego_body_vertices_xy_m']]
        last['ego_distance_to_conflict_m'] = 0.0
        last['frame'] += 1
        last['time_s'] = round(last['time_s'] + 0.05, 8)
        crossing.append(last)
        mapped = copy.deepcopy(mapping[-1])
        mapped['carla_frame'] = last['frame']
        mapped['time_s'] = last['time_s']
        mapping.append(mapped)
        traced = copy.deepcopy(trace[-1])
        traced['frame'] = last['frame']
        traced['time_s'] = last['time_s']
        trace.append(traced)
    if kind != 'missing_evidence':
        write_rows(output / 'crossing_history.jsonl', crossing)
    write_rows(output / 'trace.jsonl', trace)
    write_rows(output / 'video_frames.jsonl', mapping)
    if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT'):
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports')
    sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import assess_physical
    assessed = assess_physical(output, config)
    status = assessed['physical_checks']['maneuver']['status']
    if status != KINDS[kind]:
        raise ValueError(f'{kind}: expected {KINDS[kind]}, observed {status}')
    result = {'format': 'c158196-257-2-physical-diagnostic',
              'case_id': config['selected_case_id'], 'fixture_kind': kind,
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'physical_checks': assessed['physical_checks'],
              'maneuver_completed': assessed['maneuver_completed'],
              'realized_observables': assessed['realized_observables'],
              'setup_confirmed': assessed['setup_confirmed'],
              'legal_conclusion': 'unresolved'}
    (output / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'fixture_kind': kind,
                      'status': status, 'setup_status': assessed['physical_checks']['setup']['status']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', required=True)
    parser.add_argument('--kind', choices=sorted(KINDS), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.case_suffix, args.kind, args.output)
