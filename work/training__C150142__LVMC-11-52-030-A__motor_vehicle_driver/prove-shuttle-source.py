"""Exercise signed-bus long finalizers on explicit synthetic Native source rows."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location('tour_bus_source_helpers',
                                            ROOT / 'prove-tour-bus-saved-source.py')
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report


def prove(case, candidate):
    if case not in tuple(service + '_' + boundary
                         for service in ('shuttle_bus', 'rtc_bus')
                         for boundary in ('below', 'at', 'above', 'no_loading')):
        raise ValueError('Unsupported signed-bus case')
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unsupported candidate')
    base = ROOT / ('selected-primary' if candidate == 'primary' else
                   'selected-fallbacks') / case
    if candidate != 'primary':
        base /= candidate
    package = json.loads((base / 'construction.json').read_text())
    case_id = ROOT.name + '__' + case
    if package['case_id'] != case_id:
        raise ValueError('Construction case changed')
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                     prefix='c150142-shuttle-source-') as temporary:
        stage = Path(temporary) / 'positive'
        SOURCE.materialize(stage, package)
        SOURCE.source_rows(stage)
        actual = SOURCE.run(stage)
        if actual.returncode:
            raise AssertionError('Shuttle finalizer failed: ' + actual.stderr[-1200:])
        config = json.loads((stage / 'config.json').read_text())
        report = json.loads((stage / 'analysis-report.json').read_text())
        contract = json.loads((ROOT / 'selected-primary' / case /
                               'selected-measurement-contracts' /
                               (case + '.json')).read_text())
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        dispositions = [dict(row) for row in plan['requirement_dispositions']]
        requirement = 'text-5' if case.startswith('rtc_bus_') else 'text-4'
        for row in dispositions:
            row['status'] = ('selected_required' if row['requirement'] == requirement
                             else 'exception_pending')
        validate(contract, dispositions, (stage / 'finalize_selected.py').read_text(),
                 case_id)
        verify_report(contract, report, stage)
        observed = report['measurements']['signed_curb_observation']['value']
        if (abs(observed['red_curb_stationary_duration_s'] -
                config['requested_stationary_duration_s']) > 1e-9 or
                observed['duration_relative_to_30_minutes'] != config['requested_boundary'] or
                len(observed['recorded_activity_events']) !=
                (0 if config['activity_request'] is None else 1) or
                observed['legal_verdict'] is not None):
            raise AssertionError('Source-derived shuttle measurement differs')
        missing = ('native-passenger-inventory.jsonl' if config['activity_request'] is None
                   else 'native-passenger-actors.jsonl')
        negative = Path(temporary) / 'negative'
        SOURCE.materialize(negative, package)
        SOURCE.source_rows(negative)
        (negative / missing).unlink()
        rejected = SOURCE.run(negative)
        if rejected.returncode == 0 or 'Missing required source: ' + missing not in rejected.stderr:
            raise AssertionError('Missing passenger source accepted')
        return {'case_id': case_id, 'candidate': candidate,
                'source_kind': 'synthetic_native_sample',
                'measured_duration_s': observed['red_curb_stationary_duration_s'],
                'boundary': observed['duration_relative_to_30_minutes'],
                'activity_events': len(observed['recorded_activity_events']),
                'missing_passenger_source_rejected': True,
                'draft_text4_contract_passed': True,
                'media_decoded': False, 'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.candidate), sort_keys=True))
