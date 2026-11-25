"""Exercise pinned physical completion and closure on synthetic source fixtures."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from overpass_source import sha

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SAFE = (REPO / '.runtime-work').resolve()
OUTPUT_ROOT = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not OUTPUT_ROOT.is_relative_to(SAFE):
    raise RuntimeError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def lines(path, rows):
    Path(path).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def fixture(root, config, source, context, kind):
    root.mkdir()
    write(root / 'config.json', config)
    rows = [json.loads(line) for line in source.read_text().splitlines() if line]
    if kind == 'incomplete_motion':
        rows = json.loads(json.dumps(rows))
        first_y = rows[0]['pedestrian_xyz_m'][1]
        for row in rows:
            row['pedestrian_xyz_m'][1] = first_y + .1 * (row['pedestrian_xyz_m'][1] - first_y)
    lines(root / 'trace.jsonl', [{'frame': row['frame'], 'time_s': row['time_s'],
                                  'position_m': row['pedestrian_xyz_m']} for row in rows])
    lines(root / 'video_frames.jsonl', [{'video_frame': i, 'carla_frame': row['frame'],
                                         'time_s': row['time_s']} for i, row in enumerate(rows)])
    if kind != 'missing_evidence':
        lines(root / 'body-history.jsonl', rows)
    (root / 'reviewed-site.json').write_bytes(context.read_bytes())
    write(root / 'acquisition-provenance.json',
          {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    result = physical_result(root, {'case_id': config['selected_case_id'], 'target_checks': []})
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if (result['physical_checks']['maneuver']['status'] != expected or
            result['maneuver_completed'] != (expected == 'met') or
            result['provenance_kind'] != 'synthetic_fixture' or
            result['diagnostic_fixture'] is not True):
        raise AssertionError('pinned physical completion differs: ' + kind)
    return result


def lifecycle(root, construction):
    root.mkdir()
    write(root / 'construction.json', construction)
    (root / 'runner.py').write_text('# synthetic lifecycle source\n')
    lines(root / 'trace.jsonl', [{'frame': 0}])
    lines(root / 'video_frames.jsonl', [{'carla_frame': 0, 'video_frame': 0, 'time_s': 0}])
    write(root / 'acquisition-provenance.json',
          {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    try:
        record_native_exit(root)
    except Exception:
        pass
    else:
        raise AssertionError('Native exit accepted before capture closure')
    seal = seal_capture(root, frames=1, restoration={'restored': True}, errors=[],
                        encoder_exit_codes={name: 0 for name in
                        ('overview', 'approach', 'reference_corner', 'driver_reference')})
    record_native_exit(root)
    receipt = root / 'owner-release.json'
    try:
        acknowledge_owner_release(root, receipt, False)
    except ValueError:
        pass
    else:
        raise AssertionError('unacknowledged owner release accepted')
    acknowledge_owner_release(root, receipt, True)
    return seal['events'] + ['native_exit', 'owner_released', 'saved_processing_started']


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    command = ('SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c188132-site-runtime '
               'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + HERE.name + '/prove_physical.py')
    for entry in manifest['cases']:
        variant = entry['case_id'].split('__')[-1]
        folder = HERE / 'cases' / variant
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        output = SAFE / ('c188132-compat-yield-v7' if variant == 'yield_before_vehicle'
                         else 'c188132-compat-' + variant + '-v1')
        with tempfile.TemporaryDirectory(dir=SAFE, prefix='c188132-physical-') as temp:
            root = Path(temp)
            fixtures = []
            for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
                result = fixture(root / kind, config, output / 'body-history.jsonl',
                                 output / 'reviewed-site.json', kind)
                result_path = folder / ('physical-' + kind + '.json')
                log_path = folder / ('physical-' + kind + '.log')
                write(result_path, result)
                log_path.write_text('Pinned physical_result: ' + entry['case_id'] + ' ' + kind +
                                    ' = ' + result['physical_checks']['maneuver']['status'] +
                                    '; synthetic diagnostic only.\n')
                fixtures.append({'kind': kind, 'command': command, 'exit_code': 0,
                                 'log': str(log_path.relative_to(HERE)), 'log_sha256': sha(log_path),
                                 'result': str(result_path.relative_to(HERE)), 'result_sha256': sha(result_path)})
            events = lifecycle(root / 'lifecycle', construction)
        log = folder / 'physical-lifecycle.log'
        log.write_text('Pinned closure order on synthetic sources.\n' + ' -> '.join(events) + '\n')
        receipt = {'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': events, 'exit_code': 0,
                                 'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}}
        proof_path = folder / 'physical-preparation.json'
        write(proof_path, receipt)
        entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(HERE)),
                                         'sha256': sha(proof_path)}
        print(variant, 'physical three outcomes and lifecycle passed')
    write(manifest_path, manifest)


if __name__ == '__main__':
    main()
