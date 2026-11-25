"""Exercise three source-bound CPU physical-assessor outcomes for six new cases."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
         'missing_evidence': 'unverified'}


def _rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def run(suffix, kind, output):
    if kind not in KINDS or suffix not in (
            'officer_controls_go', 'officer_controls_hold',
            'officer_present_inactive', 'stop_line_reference',
            'crosswalk_reference', 'nearest_view_reference'):
        raise ValueError('Select exact officer/reference case and outcome')
    construction = ROOT / 'cases' / (suffix + '-officer-reference-construction.json')
    bundle = json.loads(construction.read_text())
    config = json.loads(next(item['content'] for item in bundle['files']
                             if item['path'] == 'config.json'))
    spec = json.loads((ROOT / 'cases' /
                       (suffix + '-officer-reference-diagnostic-sources.json')).read_text())
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'config.json').write_text(json.dumps(config, sort_keys=True) + '\n')
    history = _rows(spec['files']['officer_reference_history.jsonl'])
    if kind == 'complete_motion':
        final = copy.deepcopy(history[-1])
        final['ego_body_vertices_xy_m'] = [
            [point[0] + 1.0, point[1]] for point in final['ego_body_vertices_xy_m']]
        history[-1] = final
    if kind != 'missing_evidence':
        (output / 'officer_reference_history.jsonl').write_text(''.join(
            json.dumps(row, separators=(',', ':'), sort_keys=True) + '\n'
            for row in history))
    (output / 'trace.jsonl').write_text(spec['files']['trace.jsonl'])
    (output / 'video_frames.jsonl').write_text(spec['files']['video_frames.jsonl'])
    if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT'):
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import assess_physical
    assessed = assess_physical(output, config)
    status = assessed['physical_checks']['maneuver']['status']
    if status != KINDS[kind]:
        raise ValueError(f'{suffix} {kind}: expected {KINDS[kind]}, got {status}')
    result = {'format': 'c158196-officer-reference-physical-diagnostic',
              'case_id': config['selected_case_id'], 'fixture_kind': kind,
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'construction_sha256': hashlib.sha256(construction.read_bytes()).hexdigest(),
              'source_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for name, path in ((p.name, p) for p in output.iterdir())
                                if path.is_file()},
              'physical_checks': assessed['physical_checks'],
              'realized_observables': assessed['realized_observables'],
              'maneuver_completed': assessed['maneuver_completed'],
              'legal_conclusion': 'unresolved'}
    (output / 'result.json').write_text(json.dumps(result, indent=2,
                                                   allow_nan=False) + '\n')
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', required=True)
    parser.add_argument('--kind', required=True, choices=sorted(KINDS))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(run(args.case_suffix, args.kind, args.output))
