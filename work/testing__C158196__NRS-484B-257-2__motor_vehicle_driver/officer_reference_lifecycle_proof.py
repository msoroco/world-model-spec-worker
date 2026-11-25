"""Exercise 600-frame officer/reference capture and saved-owner lifecycle order."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = {'officer_controls_go', 'officer_controls_hold',
            'officer_present_inactive', 'stop_line_reference',
            'crosswalk_reference', 'nearest_view_reference'}


def run(suffix):
    if suffix not in SUFFIXES:
        raise ValueError('Unknown exact officer/reference case')
    private = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    allowed = (REPO / '.runtime-work').resolve()
    if private != allowed and allowed not in private.parents:
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    construction = json.loads((ROOT / 'cases' /
                               (suffix + '-officer-reference-construction.json')).read_text())
    spec = json.loads((ROOT / 'cases' /
                       (suffix + '-officer-reference-diagnostic-sources.json')).read_text())
    saved = json.loads((ROOT / 'cases' /
                        (suffix + '-officer-reference-processing.json')).read_text())
    if (not construction['case_id'].endswith('__' + suffix) or
            saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != construction['case_id']):
        raise ValueError('Exact current-runtime recorded-only proof missing')
    sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
                                                  acknowledge_owner_release)
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c158196-officer-lifecycle-',
                                     dir=private) as name:
        attempt = Path(name)
        (attempt / 'construction.json').write_text(json.dumps(construction) + '\n')
        runner = next(f['content'] for f in construction['files']
                      if f['path'] == 'runner.py')
        (attempt / 'runner.py').write_text(runner)
        for source in ('trace.jsonl', 'video_frames.jsonl'):
            (attempt / source).write_text(spec['files'][source])
        (attempt / 'acquisition-provenance.json').write_text(json.dumps(
            {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        try:
            seal_capture(attempt, frames=600, restoration={'restored': True},
                         errors=[], encoder_exit_codes={'fixture_encoder': 1})
        except ValueError as error:
            if 'unclosed/failed encoders' not in str(error):
                raise
        else:
            raise ValueError('Failed encoder incorrectly sealed')
        seal = seal_capture(attempt, frames=600, restoration={'restored': True},
                            errors=[], encoder_exit_codes={'fixture_encoder': 0})
        try:
            acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
        except ValueError as error:
            if 'Native process has not exited' not in str(error):
                raise
        else:
            raise ValueError('Owner release incorrectly preceded Native exit')
        exited = record_native_exit(attempt)
        owner = acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
        events = seal['events'] + [exited['event'], owner['event'], saved['events'][0]]
        expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                    'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected:
            raise ValueError('Saved processing order differs')
        return {'case_id': construction['case_id'], 'events': events,
                'diagnostic_fixture': True, 'failed_encoder_rejected': True,
                'premature_release_rejected': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', required=True)
    print(json.dumps(run(parser.parse_args().case_suffix)))
