"""Exercise original-source completion and ownership gates on CPU fixtures."""
import argparse
import json
import os
import shutil
from pathlib import Path

from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import acknowledge_owner_release, record_native_exit

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def main(case, output):
    source = ROOT / 'diagnostic' / case / 'sources'
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    assert '.runtime-work' in scratch.parts
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    construction = json.loads((ROOT / 'draft-roadway' / case / 'primary/construction.json').read_text())
    files = {item['path']: item['content'] for item in construction['files']}
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        stage = scratch / (case + '-' + kind)
        stage.mkdir(parents=True, exist_ok=False)
        for name in ('trace.jsonl', 'video_frames.jsonl'):
            shutil.copy2(source / name, stage / name)
        (stage / 'config.json').write_text(files['config.json'])
        if kind == 'incomplete_motion':
            rows = [json.loads(row) for row in (stage / 'trace.jsonl').read_text().splitlines()]
            for row in rows:
                row['position_m'][0] = -30
                row['position']['x'] = -30
            (stage / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        elif kind == 'missing_evidence':
            (stage / 'trace.jsonl').unlink()
        result = physical_result(stage, {'target_checks': []})
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        assert result['physical_checks']['maneuver']['status'] == expected
        assert result['maneuver_completed'] == (expected == 'met')
        assert result['provenance_kind'] == 'synthetic_fixture'
        assert result['diagnostic_fixture'] is True
        assert expected != 'met' or result['realized_observables']
        receipt = output / (kind + '-result.json')
        write(receipt, result)
        log = output / (kind + '.log')
        log.write_text('PASS ' + case + ' ' + kind + ': ' + expected + '\n')
        fixtures.append({'kind': kind, 'result': str(receipt.relative_to(ROOT)),
                         'log': str(log.relative_to(ROOT))})
    stage = scratch / (case + '-lifecycle')
    stage.mkdir(parents=True, exist_ok=False)
    for name in ('trace.jsonl', 'video_frames.jsonl'):
        shutil.copy2(source / name, stage / name)
    for name in ('config.json', 'runner.py'):
        (stage / name).write_text(files[name])
    write(stage / 'construction.json', construction)
    write(stage / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    seal = seal_capture(stage, frames=600, restoration={'restored': True}, errors=[],
                        encoder_exit_codes={camera: 0 for camera in
                                            ('overview', 'approach', 'reference_corner', 'driver_reference')})
    native_exit = record_native_exit(stage)
    owner = acknowledge_owner_release(stage, stage / 'owner-release.json', True)
    assert seal['events'] == ['capture_finished', 'encoders_closed', 'restoration_verified']
    assert native_exit['event'] == 'native_exit' and owner['event'] == 'owner_released'
    log = output / 'physical-lifecycle.log'
    log.write_text('PASS synthetic capture seal, Native exit, owner release, then saved processing\n')
    print(json.dumps({'case': case, 'fixtures': fixtures,
                      'lifecycle_log': str(log.relative_to(ROOT)),
                      'events': seal['events'] + [native_exit['event'], owner['event'],
                                                  'saved_processing_started']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('probe_01', 'probe_02'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.case, args.output)
