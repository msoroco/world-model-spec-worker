"""Prove three engineering motion outcomes without claiming a legal result."""
import hashlib
import json
from pathlib import Path
import sys

from worker_exchange.native_output import assess_physical

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO/'.runtime-work'/'c110969-physical-fixtures'
SUFFIXES = ('outside_reference', 'inside_stop', 'inside_stand', 'inside_park',
            'traffic_conflict', 'law_direction', 'officer_direction',
            'device_direction', 'through_motion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')


def make_fixture(path, config, kind):
    path.mkdir(parents=True, exist_ok=True)
    write_json(path/'config.json', config)
    count = config['frame_count']
    mapping = [{'video_frame': i, 'carla_frame': i+1, 'native_frame': i+1,
                'time_s': (i+1)/config['rate_hz']} for i in range(count)]
    (path/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in mapping))
    if kind != 'missing_evidence':
        distance = 120.0 if kind == 'complete_motion' else 1.0
        rows = [{'frame': i+1, 'time_s': (i+1)/config['rate_hz'],
                 'position_m': [distance*i/(count-1), 0, 0]}
                for i in range(count)]
        (path/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))


def prove_case(suffix):
    construction = HERE/('construction-'+suffix+'.json')
    package = json.loads(construction.read_text())
    config = json.loads(next(item['content'] for item in package['files']
                             if item['path'] == 'config.json'))
    proofs = []
    for kind, expected in (('complete_motion', 'met'),
                           ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')):
        fixture = SCRATCH/suffix/kind
        if fixture.exists():
            import shutil
            shutil.rmtree(fixture)
        make_fixture(fixture, config, kind)
        assessment = assess_physical(fixture, config)
        status = assessment['physical_checks']['maneuver']['status']
        if status != expected or assessment['maneuver_completed'] != (expected == 'met'):
            raise AssertionError(f'{suffix} {kind}: {status} != {expected}')
        result = {'case_id': package['case_id'], 'kind': kind,
                  'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                  'physical_checks': assessment['physical_checks'],
                  'realized_observables': assessment['realized_observables'],
                  'maneuver_completed': assessment['maneuver_completed'],
                  'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
        target = HERE/'cases'/suffix/('physical-'+kind+'.json')
        write_json(target, result)
        log = HERE/'cases'/suffix/('physical-'+kind+'.log')
        log.write_text(f'{package["case_id"]} {kind}: {status}; synthetic engineering motion only\n')
        proofs.append({'kind': kind, 'command': '.venv-cpu/bin/python '+str(Path(__file__).relative_to(REPO))+' '+suffix,
                       'exit_code': 0, 'log': str(log.relative_to(HERE)),
                       'log_sha256': sha(log), 'result': str(target.relative_to(HERE)),
                       'result_sha256': sha(target)})
    lifecycle = ['capture_finished', 'encoders_closed', 'restoration_verified',
                 'native_exit', 'owner_released', 'saved_processing_started']
    life_log = HERE/'cases'/suffix/'physical-lifecycle.log'
    life_log.write_text('CPU modeled lifecycle order; original Native closure remains unobserved: '
                        + ', '.join(lifecycle)+'\n')
    receipt = {'format': 'intersection-physical-preparation-v1',
               'construction_sha256': sha(construction), 'fixtures': proofs,
               'lifecycle': {'events': lifecycle, 'exit_code': 0,
                             'provenance_kind': 'synthetic_fixture',
                             'log': str(life_log.relative_to(HERE)),
                             'log_sha256': sha(life_log)},
               'scope': 'synthetic engineering travel progress, not intersection-stop or legal acceptance'}
    receipt_path = HERE/'cases'/suffix/'physical-preparation.json'
    write_json(receipt_path, receipt)
    print(suffix, sha(receipt_path), flush=True)


if __name__ == '__main__':
    SCRATCH.mkdir(parents=True, exist_ok=True)
    suffixes = sys.argv[1:] or SUFFIXES
    if any(s not in SUFFIXES for s in suffixes):
        raise ValueError('Unknown exact case suffix')
    for suffix in suffixes:
        prove_case(suffix)
