"""Synthetic source fixtures for pinned physical and lifecycle preparation."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.native_output import physical_result, seal_capture  # noqa: E402
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release  # noqa: E402


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def prove(case, output_dir):
    manifest = json.loads((HERE/'execution-manifest.json').read_text())
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Exact selected case required')
    construction_path = HERE/entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Primary construction changed')
    construction = json.loads(construction_path.read_text())
    files = {f['path']: f['content'] for f in construction['files']}
    config = json.loads(files['config.json'])
    if (config.get('physical_completion', {}).get('minimum_progress_m') != 12 or
            config.get('physical_completion', {}).get('criterion') != 'travel_progress' or
            bool(config.get('reverse_motion')) != case.endswith('against_designation')):
        raise ValueError('Exact route-aware physical criterion differs')
    source = HERE/('cases/against-diagnostic.json' if case.endswith('against_designation') else 'diagnostic.json')
    diagnostic = json.loads(source.read_text())['files']
    saved = json.loads((HERE/entry['saved_processing']['receipt']).read_text())
    if (not saved['passed'] or not saved['recorded_only'] or
            saved['native_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Current saved processing receipt missing')
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        with tempfile.TemporaryDirectory(prefix='c147311-physical-') as temp:
            attempt = Path(temp)
            (attempt/'config.json').write_text(files['config.json'])
            (attempt/'video_frames.jsonl').write_text(diagnostic['video_frames.jsonl'])
            (attempt/'trace.jsonl').write_text(diagnostic['trace.jsonl'])
            write(attempt/'acquisition-provenance.json', {'provenance_kind':'synthetic_fixture',
                  'diagnostic_fixture':True, 'scope':'synthetic CPU classifier test only'})
            if kind == 'missing_evidence':
                (attempt/'trace.jsonl').unlink()
            else:
                rows = [json.loads(line) for line in diagnostic['trace.jsonl'].splitlines() if line]
                sign = -1 if config.get('reverse_motion') else 1
                first = rows[0]['position_m'][0]
                distance = 15 if kind == 'complete_motion' else 2
                for index, row in enumerate(rows):
                    x = first + sign*distance*index/(len(rows)-1)
                    row['position_m'][0] = x
                    row['position']['x'] = x
                (attempt/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            result = physical_result(attempt, {'target_checks':[]})
            expected = {'complete_motion':'met','incomplete_motion':'not_met',
                        'missing_evidence':'unverified'}[kind]
            check = result['physical_checks']['maneuver']
            if (check['status'] != expected or result['maneuver_completed'] != (expected == 'met') or
                    not check['method'] or not check['sources'] or result['physical_acceptance_claimed']):
                raise AssertionError('Physical fixture outcome differs: '+kind)
            write(output_dir/(kind+'.json'), result)
            results[kind] = expected
    with tempfile.TemporaryDirectory(prefix='c147311-lifecycle-') as temp:
        attempt = Path(temp)
        (attempt/'construction.json').write_text(construction_path.read_text())
        (attempt/'runner.py').write_text(files['runner.py'])
        (attempt/'trace.jsonl').write_text(diagnostic['trace.jsonl'])
        (attempt/'video_frames.jsonl').write_text(diagnostic['video_frames.jsonl'])
        try:
            seal_capture(attempt, frames=9, restoration={'restored':True}, errors=[],
                         encoder_exit_codes={'fixture_encoder':1})
        except ValueError as error:
            if 'unclosed/failed encoders' not in str(error):
                raise
        else:
            raise AssertionError('Failed encoder was sealed')
        seal = seal_capture(attempt, frames=9, restoration={'restored':True}, errors=[],
                            encoder_exit_codes={'fixture_encoder':0})
        try:
            acknowledge_owner_release(attempt, attempt/'owner-release.json', True)
        except ValueError as error:
            if 'Native process has not exited' not in str(error):
                raise
        else:
            raise AssertionError('Owner release preceded Native exit')
        native = record_native_exit(attempt)
        owner = acknowledge_owner_release(attempt, attempt/'owner-release.json', True)
        events = seal['events']+[native['event'], owner['event'], saved['events'][0]]
        if events != ['capture_finished','encoders_closed','restoration_verified',
                      'native_exit','owner_released','saved_processing_started']:
            raise AssertionError('Native lifecycle event order differs')
        write(output_dir/'lifecycle.json', {'case_id':case, 'events':events,
              'failed_encoder_rejected':True, 'premature_release_rejected':True,
              'saved_processing_sha256':sha(HERE/entry['saved_processing']['receipt']),
              'diagnostic_fixture_only':True})
    return {'case_id':case, 'diagnostic_fixture_only':True, 'physical_statuses':results,
            'lifecycle_events':events, 'physical_acceptance_claimed':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.output_dir), sort_keys=True))
