"""Prove selected full-pass motion outcomes on saved CPU diagnostic sources."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from scenario_pipeline.worker_exchange.native_output import physical_result, seal_capture
from scenario_pipeline.worker_exchange.saved_processing import acknowledge_owner_release, record_native_exit

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(suffix):
    family = 'draft-bicycle' if suffix.startswith('bicycle') else 'draft-ebike'
    construction_path = ROOT / family / suffix / 'primary/construction.json'
    construction = json.loads(construction_path.read_text())
    files = {item['path']: item['content'] for item in construction['files']}
    source = ROOT / 'diagnostic' / suffix / 'sources'
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    assert '.runtime-work' in scratch.parts
    output = ROOT / 'selected-physical' / suffix
    output.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for kind, expected in (('complete_motion', 'met'), ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')):
        stage = scratch / (suffix + '-' + kind)
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir()
        for name in ('participant-poses.jsonl', 'trace.jsonl', 'video_frames.jsonl'):
            shutil.copy2(source / name, stage / name)
        (stage / 'config.json').write_text(files['config.json'])
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in (stage / 'participant-poses.jsonl').read_text().splitlines()]
            for row in rows:
                row['rider_body_xy_m'] = [[-100.0, y] for _, y in row['rider_body_xy_m']]
            (stage / 'participant-poses.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        if kind == 'missing_evidence':
            (stage / 'participant-poses.jsonl').unlink()
        result = physical_result(stage, {'target_checks': []})
        assert result['physical_checks']['maneuver']['status'] == expected
        assert result['maneuver_completed'] == (expected == 'met')
        assert result['provenance_kind'] == 'synthetic_fixture' and result['diagnostic_fixture'] is True
        assert expected != 'met' or result['realized_observables']
        result_path = output / (kind + '-result.json')
        log_path = output / (kind + '.log')
        write(result_path, result)
        log_path.write_text('PASS ' + suffix + ' ' + kind + ' ' + expected + '\n')
        fixtures.append({'kind': kind, 'command': 'native/prove_physical.py --case ' + suffix,
                         'exit_code': 0, 'result': str(result_path.relative_to(ROOT)),
                         'result_sha256': sha(result_path), 'log': str(log_path.relative_to(ROOT)),
                         'log_sha256': sha(log_path)})
    stage = scratch / (suffix + '-lifecycle')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    for name in ('participant-poses.jsonl', 'trace.jsonl', 'video_frames.jsonl'):
        shutil.copy2(source / name, stage / name)
    for name in ('config.json', 'runner.py'):
        (stage / name).write_text(files[name])
    write(stage / 'construction.json', construction)
    write(stage / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    seal = seal_capture(stage, frames=600, restoration={'restored': True}, errors=[],
                        encoder_exit_codes={name: 0 for name in
                                            ('overview', 'approach', 'reference_corner', 'driver_reference')})
    native_exit = record_native_exit(stage)
    owner = acknowledge_owner_release(stage, stage / 'owner-release.json', True)
    events = seal['events'] + [native_exit['event'], owner['event'], 'saved_processing_started']
    assert events == ['capture_finished', 'encoders_closed', 'restoration_verified',
                      'native_exit', 'owner_released', 'saved_processing_started']
    lifecycle_log = output / 'lifecycle.log'
    lifecycle_log.write_text('PASS synthetic capture, restoration, Native exit and owner release\n')
    receipt = {'format': 'c146108-physical-preparation-v1',
               'case_id': construction['case_id'], 'construction_sha256': sha(construction_path),
               'fixtures': fixtures, 'lifecycle': {'events': events, 'exit_code': 0,
               'log': str(lifecycle_log.relative_to(ROOT)), 'log_sha256': sha(lifecycle_log)},
               'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    receipt_path = output / 'physical-preparation.json'
    write(receipt_path, receipt)
    print(json.dumps({'case_id': construction['case_id'], 'receipt_sha256': sha(receipt_path),
                      'statuses': [f['kind'] for f in fixtures]}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('bicycle_pass_wide', 'electric_bicycle_pass_wide',
                                            'electric_bicycle_pass_narrow'), required=True)
    main(parser.parse_args().case)
