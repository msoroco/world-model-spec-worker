"""Exercise pinned source-bound physical checker on three synthetic outcomes.

Each exact case uses its selected config, with a four-frame diagnostic duration.
This tests completion classification and lifecycle ordering, never realization.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(REPO / '.runtime-work' / 'owner150142' / 'physical'))
sys.path.insert(0, str(REPO / 'runtime'))
from scenario_pipeline.worker_exchange.native_output import assess_physical
from scenario_pipeline.worker_exchange.physical_preparation import validate

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def prove(case):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact selected case')
    construction = json.loads((HERE / entry['construction']).read_text())
    config = json.loads(next(f['content'] for f in construction['files']
                             if f['path'] == 'config.json'))
    slug = case.rsplit('__', 1)[1]
    scratch = REPO / '.runtime-work' / 'owner150142' / 'physical' / slug
    command = ('PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.runtime-work '
               'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/owner150142/physical '
               '.venv-cpu/bin/python '
               + str(Path(__file__).relative_to(REPO)) + ' --case ' + case)
    fixtures = []
    log_lines = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        root = scratch / kind
        root.mkdir(parents=True, exist_ok=True)
        diagnostic = dict(config, duration_s=0.2, rate_hz=20,
                          requested_speed_mps=5)
        write(root / 'config.json', diagnostic)
        mapping = [{'video_frame': i, 'carla_frame': 100 + i,
                    'time_s': i / 20} for i in range(4)]
        (root / 'video_frames.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in mapping))
        positions = ([0.0, 0.8, 1.6, 2.4] if kind == 'complete_motion'
                     else [0.0] * 4)
        if kind != 'missing_evidence':
            trace = [{'frame': 100 + i, 'time_s': i / 20,
                      'position_m': [x, 0.0, 0.0]} for i, x in enumerate(positions)]
            (root / 'trace.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in trace))
        elif (root / 'trace.jsonl').exists():
            (root / 'trace.jsonl').unlink()
        assessment = assess_physical(root, diagnostic)
        status = assessment['physical_checks']['maneuver']['status']
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected or assessment['maneuver_completed'] != (expected == 'met'):
            raise ValueError('Pinned physical status differs: ' + case + ' ' + kind)
        source = assessment['physical_checks']['maneuver']['sources']
        result = {'case_id': case, 'fixture_kind': kind,
                  'physical_checks': {'maneuver': assessment['physical_checks']['maneuver']},
                  'maneuver_completed': assessment['maneuver_completed'],
                  'realized_observables': {'diagnostic_sampled_motion': {
                      'source_sha256': source.get('trace.jsonl'),
                      'sample_count': 4}} if expected == 'met' else {},
                  'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                  'original_native_observed': False, 'legal_verdict_claimed': False}
        path = HERE / 'physical-fixtures' / slug / (kind + '.json')
        write(path, result)
        fixtures.append({'kind': kind, 'command': command,
                         'log': 'physical-fixtures/' + slug + '/proof.log',
                         'exit_code': 0, 'result': str(path.relative_to(HERE)),
                         'result_sha256': sha(path)})
        log_lines.append(kind + ': ' + status)
    if EVENTS != ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']:
        raise ValueError('Capture lifecycle ordering changed')
    life_path = HERE / 'physical-fixtures' / slug / 'lifecycle.json'
    write(life_path, {'events': EVENTS, 'case_id': case, 'synthetic_fixture': True})
    log = HERE / 'physical-fixtures' / slug / 'proof.log'
    log.write_text('\n'.join(log_lines + ['lifecycle: ' + ','.join(EVENTS)]) + '\n')
    for item in fixtures:
        item['log_sha256'] = sha(log)
    life = {'events': EVENTS, 'command': command, 'log': str(log.relative_to(HERE)),
            'log_sha256': sha(log), 'exit_code': 0,
            'result': str(life_path.relative_to(HERE)),
            'result_sha256': sha(life_path)}
    receipt = {'format': 'c150142-physical-cpu-fixture-proof-v1',
               'case_id': case, 'construction_sha256': entry['construction_sha256'],
               'diagnostic_fixture': True, 'original_native_observed': False,
               'physical_acceptance_claimed': False, 'fixtures': fixtures,
               'lifecycle': life}
    receipt_path = HERE / 'physical-preparation' / (slug + '.json')
    write(receipt_path, receipt)
    draft = dict(entry, physical_preparation={
        'receipt': str(receipt_path.relative_to(HERE)), 'sha256': sha(receipt_path)})
    validate(REPO, HERE, draft)
    return {'case_id': case, 'receipt': str(receipt_path.relative_to(HERE)),
            'sha256': sha(receipt_path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    args = parser.parse_args()
    cases = [args.case] if args.case else [e['case_id'] for e in
             json.loads((HERE / 'execution-manifest.json').read_text())['cases']]
    results = [prove(case) for case in cases]
    if args.case:
        print(json.dumps(results[0], sort_keys=True))
    else:
        index = {'format': 'c150142-physical-preparation-cpu-index-v1',
                 'passed': True, 'cases': results, 'source_kind': 'synthetic_fixture',
                 'original_native_observed': False,
                 'physical_acceptance_claimed': False}
        path = HERE / 'current-physical-preparation-cpu-index.json'
        write(path, index)
        print(json.dumps({'cases': len(results), 'index_sha256': sha(path)}, sort_keys=True))
