"""Recorded-only original alley-hour finalization; no requested-duration verdict."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from measure_alley_parking import measure

SOURCE_KEYS = ('native_map_sha256', 'alley_boundary_sha256', 'vehicle_identity_sha256',
               'civil_time_source_sha256', 'lawful_parking_review_sha256')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('st.alley', 'drv.standing_or_parked', 'kin.time', 'env.civil_time',
            'rel.occupies', 'kin.position')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rolling_hour_alley_parking(context, ledger, frames):
    return measure(context, ledger, frames)

def run(attempt, output):
    attempt, output = Path(attempt), Path(output)
    required = ('original_alley_context.json', 'original_parking_ledger.json',
                'alley-capture.jsonl', 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl')
    for name in required:
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    require(not output.exists(), 'Choose a fresh analysis report')
    config = json.loads((attempt / 'config.json').read_text())
    context = json.loads((attempt / required[0]).read_text())
    ledger = json.loads((attempt / required[1]).read_text())
    require(context.get('parking_ledger_sha256') == sha(attempt / required[1]),
            'Original hour ledger source hash changed')
    for key in SOURCE_KEYS:
        document = context.get('source_documents', {}).get(key)
        require(isinstance(document, str) and document.startswith('original-') and
                '/' not in document and '\\' not in document,
                'Missing original source document: ' + key)
        require((attempt / document).is_file(), 'Missing required source: ' + document)
        require(sha(attempt / document) == context.get(key),
                'Original source document hash changed: ' + key)
    diagnostic = os.environ.get('SCENARIO_DIAGNOSTIC_FIXTURE') == '1'
    require(context.get('assignment_id') == config['case_id'].rsplit('__', 1)[0],
            'Original alley assignment differs')
    if diagnostic:
        require(context.get('source_kind') == 'synthetic_cpu_alley_fixture',
                'Diagnostic fixture provenance missing')
        context['source_kind'] = 'original_native_alley_parking_ledger'
    else:
        require(context.get('source_kind') == 'original_native_alley_parking_ledger',
                'Original alley parking source missing')
    require(context.get('otherwise_lawful_review') == 'independently_reviewed' and
            context.get('alley_status') == 'source_surveyed_alley',
            'Original alley and lawful source review missing')
    frames = [json.loads(s) for s in (attempt / 'alley-capture.jsonl').read_text().splitlines() if s]
    finding = rolling_hour_alley_parking(context, ledger, frames)
    require(tuple(c['name'] for c in config['recording_description']['channels']) == CHANNELS,
            'Selected source channels changed')
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    evidence = []
    for name in CHANNELS:
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in frames:
                if name == 'st.alley':
                    value = {'source_surveyed_alley': context['alley_status'],
                             'boundary_source_sha256': context['alley_boundary_sha256']}
                elif name == 'drv.standing_or_parked':
                    value = {'vehicle_id': row['vehicle_id'],
                             'observed_speed_mps': row.get('observed_speed_mps'),
                             'hour_parked_intervals': ledger['parked_intervals']}
                elif name == 'kin.time':
                    value = {'capture_time_s': row['time_s'],
                             'max_parked_seconds_in_sourced_rolling_hour': finding['max_parked_seconds_in_sourced_rolling_hour']}
                elif name == 'env.civil_time':
                    value = {'civil_time_s': row['time_s'],
                             'source_sha256': context['civil_time_source_sha256']}
                elif name == 'rel.occupies':
                    value = {'within_alley': row['within_alley'],
                             'boundary_source_sha256': context['alley_boundary_sha256']}
                else:
                    value = row.get('position_xyz_m')
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': 'structured', 'reference': 'channels/' + path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['case_id'], 'measured_values': finding,
              'target_checks': [{'target': 'parked seconds in any sourced rolling hour',
                                 'requested': config['requested_parked_seconds_in_rolling_hour'],
                                 'measured': finding['max_parked_seconds_in_sourced_rolling_hour'],
                                 'method': 'original one-hour ledger and 20 Hz four-camera Native join',
                                 'tolerance': 'source timing accuracy requires original review',
                                 'matched': False, 'physical_cause_confirmed': False,
                                 'cause_evidence': list(required)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'accepted': False,
              'termination_reason': 'Saved original source measurement; independent physical and legal review pending',
              'physical_failure_flags': ['original_source_and_physical_review_pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS] + ['raw.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    write_result(attempt, physical_result(attempt, result))
    sources = {name: sha(attempt / name) for name in required}
    sources.update({doc: sha(attempt / doc) for doc in context['source_documents'].values()})
    report = {'format': 'worker-analysis-report', 'case_id': config['case_id'],
              'measurements': {key: {'method': 'rolling_hour_alley_parking',
                                     'value': finding, 'sources': sources}
                               for key in ('alley_duration', 'rolling_one_hour', 'otherwise_lawful')},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt, args.output), sort_keys=True))
