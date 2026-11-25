"""Exercise sealed diagnostic capture and saved-processing ownership order."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def run(suffix):
    if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT'):
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    construction_path = ROOT / 'cases' / (suffix + '-construction.json')
    if suffix == 'active_signal_controls':
        construction_path = ROOT / 'construction.json'
    construction = json.loads(construction_path.read_text())
    if not construction['case_id'].endswith('__' + suffix):
        raise ValueError('Case suffix mismatch')
    spec = json.loads((ROOT / 'cases' / (suffix + '-diagnostic-sources.json')).read_text())
    saved = json.loads((ROOT / 'cases' / (suffix + '-process-saved.json')).read_text())
    if saved.get('passed') is not True or saved.get('recorded_only') is not True:
        raise ValueError('Missing selected saved-only diagnostic proof')
    sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
    private = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if private != (REPO / '.runtime-work').resolve() and (REPO / '.runtime-work').resolve() not in private.parents:
        raise ValueError('Runtime output root must be under .runtime-work')
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c158196-lifecycle-', dir=private) as name:
        attempt = Path(name)
        (attempt / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
        runner = next(item['content'] for item in construction['files'] if item['path'] == 'runner.py')
        (attempt / 'runner.py').write_text(runner)
        for source in ('trace.jsonl', 'video_frames.jsonl'):
            (attempt / source).write_text(spec['files'][source])
        (attempt / 'acquisition-provenance.json').write_text(json.dumps(
            {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        try:
            seal_capture(attempt, frames=3, restoration={'restored': True}, errors=[],
                         encoder_exit_codes={'fixture_encoder': 1})
        except ValueError as error:
            if 'unclosed/failed encoders' not in str(error):
                raise
        else:
            raise ValueError('Failed encoder incorrectly sealed')
        seal = seal_capture(attempt, frames=3, restoration={'restored': True}, errors=[],
                            encoder_exit_codes={'fixture_encoder': 0})
        try:
            acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
        except ValueError as error:
            if 'Native process has not exited' not in str(error):
                raise
        else:
            raise ValueError('Owner release incorrectly preceded Native exit')
        exit_receipt = record_native_exit(attempt)
        owner = acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
        events = seal['events'] + [exit_receipt['event'], owner['event'], saved['events'][0]]
        expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                    'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected:
            raise ValueError('Saved processing order differs')
        print(json.dumps({'case_id': construction['case_id'], 'events': events,
                          'diagnostic_fixture': True, 'failed_encoder_rejected': True,
                          'premature_release_rejected': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', required=True)
    args = parser.parse_args()
    run(args.case_suffix)
