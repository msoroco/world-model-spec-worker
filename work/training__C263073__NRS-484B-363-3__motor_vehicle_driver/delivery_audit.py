"""Independent saved-source audit for exact school-zone U-turn attempts."""
import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from native.branch_cases import CASES, FACT_TOPICS, expected_facts

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
TOPICS = ('zone_designation', 'zone_boundaries', 'school_adjacency', 'highway_status',
          'driver_identity', 'driver_control', 'vehicle_classification',
          'child_identity', 'child_location', 'school_session', 'school_operation',
          'class_hours', 'civil_time', 'beacon_configuration', 'beacon_lights', 'zone_sign')
EXCEPTIONS = ('a_no_children', 'b_not_in_session', 'c_operation_interval',
              'd_operational_beacon_class_hours', 'e_no_operational_beacon_sign')


def read(path):
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case, candidate, attempt, processing, diagnostic, omit_source):
    manifest = read(HERE / 'draft-execution-manifest.json')
    entry = next((x for x in manifest['cases'] if x['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    selected = entry if candidate == 'primary' else next((x for x in entry['candidates'] if x['id'] == candidate), None)
    if selected is None:
        raise ValueError('Unknown exact candidate')
    saved = read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != case or saved.get('candidate_id') != candidate or
            saved.get('originals_preserved') is not True or
            saved.get('native_revision', {}).get('construction_sha256') != sha(Path(attempt) / 'construction.json') or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600 or
            saved.get('physical_acceptance_claimed') is not False or
            saved.get('legal_acceptance_claimed') is not False):
        raise ValueError('Selected saved-only processing differs')
    if read(Path(attempt) / 'construction.json') != read(HERE / selected['construction']):
        raise ValueError('Materialized selected construction differs')
    stage = Path(saved['analysis_directory']).resolve()
    names = ('school-context.json', 'native-motion.jsonl', 'trace.jsonl', 'video_frames.jsonl') + tuple(n + '.mkv' for n in CAMERAS)
    hashes = {}
    for name in names:
        if name == omit_source:
            raise ValueError('Missing source: ' + name)
        hashes[name] = sha(stage / name) if (stage / name).is_file() else None
        if hashes[name] is None:
            raise ValueError('Missing source: ' + name)
    context = read(stage / 'school-context.json')
    review = context.get('independent_review', {})
    records = review.get('records', {})
    if set(records) != set(TOPICS) or set(review.get('exception_dispositions', {})) != set(EXCEPTIONS):
        raise ValueError('School-zone review coverage differs')
    for topic in TOPICS:
        record = records[topic]
        source = (stage / record['path']).resolve()
        if not source.is_relative_to(stage) or not source.is_file() or sha(source) != record['sha256']:
            raise ValueError('Independent source binding differs: ' + topic)
        hashes[record['path']] = record['sha256']
    suffix = case.rsplit('__', 1)[-1]
    branch = CASES[suffix]
    if review.get('case_context') != branch['context']:
        raise ValueError('Independent selected case context differs')
    facts = review.get('case_facts', {})
    expected_factual = expected_facts(suffix)
    if set(facts) != set(FACT_TOPICS):
        raise ValueError('Independent case facts missing')
    for key, topics in FACT_TOPICS.items():
        item = facts[key]
        if (item.get('value') != expected_factual[key] or
                item.get('source_topics') != list(topics) or
                item.get('source_sha256') != {topic: records[topic]['sha256'] for topic in topics}):
            raise ValueError('Independent case fact differs: ' + key)
    clock = review.get('operation_clock', {})
    clock_topics = ('school_operation', 'civil_time')
    if (clock.get('source_topics') != list(clock_topics) or
            clock.get('source_sha256') != {topic: records[topic]['sha256'] for topic in clock_topics}):
        raise ValueError('Independent school operation clock source binding differs')
    operation_source = read(stage / records['school_operation']['path'])
    civil_source = read(stage / records['civil_time']['path'])
    names = ('operation_ceases_at', 'next_operation_begins_at')
    if (any(operation_source.get(name) != clock.get(name) for name in names) or
            civil_source.get('civil_time_at_capture') != clock.get('civil_time_at_capture')):
        raise ValueError('Independent school operation clock differs from original sources')
    end, next_start, civil = (datetime.fromisoformat(clock[name]) for name in
                              (*names, 'civil_time_at_capture'))
    if not end < next_start or any(value.utcoffset() is None for value in (end, next_start, civil)):
        raise ValueError('Independent school operation chronology differs')
    lower, upper = end + timedelta(minutes=30), next_start - timedelta(minutes=30)
    if not lower < upper or civil in (lower, upper):
        raise ValueError('Independent school operation endpoint legally unresolved')
    inside = lower < civil < upper
    if inside != facts['half_hour_operation_interval']['value']:
        raise ValueError('Independent school operation interval fact differs')
    if review['exception_dispositions']['c_operation_interval']['status'] != (
            'applies' if inside else 'does_not_apply'):
        raise ValueError('Independent school operation interval disposition differs')
    beacon = review.get('beacon_definition', {})
    beacon_topics = ('beacon_configuration', 'beacon_lights', 'zone_sign')
    if (type(beacon.get('yellow_light_count')) is not int or beacon['yellow_light_count'] < 2 or
            beacon.get('flashes_alternately') is not True or beacon.get('used_with_sign') is not True or
            beacon.get('source_topics') != list(beacon_topics) or
            beacon.get('source_sha256') != {topic: records[topic]['sha256'] for topic in beacon_topics}):
        raise ValueError('Statutory speed-limit-beacon definition source differs')
    target_exception = branch['target_exception']
    dispositions = review['exception_dispositions']
    if target_exception is None:
        if any(item['status'] != 'does_not_apply' for item in dispositions.values()):
            raise ValueError('Active/reference exception source review differs')
    elif dispositions[target_exception]['status'] != 'applies':
        raise ValueError('Selected exception source review differs')
    report = read(stage / 'analysis-report.json')
    measurements = report.get('measurements', {})
    expected = {'school_zone_turn_observation'} | {'exception_' + name for name in EXCEPTIONS}
    if set(measurements) != expected:
        raise ValueError('Separate exception measurements missing')
    for key in expected:
        item = measurements[key]
        if any(hashes.get(name) != checksum for name, checksum in item.get('sources', {}).items()):
            raise ValueError('Measured original source changed: ' + key)
        if key.startswith('exception_') and item['value']['legal_verdict'] != 'unresolved':
            raise ValueError('Exception legal verdict invented')
    result = read(stage / 'result.json')
    if result.get('case_id') != case or result.get('legal_verdict_claimed') is True:
        raise ValueError('Result identity or legal claim differs')
    provenance = read(Path(attempt) / 'acquisition-provenance.json')
    if diagnostic:
        if provenance.get('provenance_kind') != 'synthetic_fixture' or provenance.get('diagnostic_fixture') is not True:
            raise ValueError('Diagnostic proof lacks synthetic provenance')
    elif provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True:
        raise ValueError('Actual Native acquisition required')
    return {'format': 'c263073-independent-delivery-audit-v1',
            'case_id': case, 'candidate_id': candidate,
            'construction_sha256': selected['construction_sha256'],
            'saved_processing_sha256': sha(processing),
            'source_sha256': hashes, 'diagnostic_only': diagnostic,
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source', choices=('school-context.json', 'native-motion.jsonl', 'driver_reference.mkv'))
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError('Source omission is diagnostic only')
    value = audit(args.case, args.candidate, args.attempt, args.processing, args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError('Retain previous delivery audit')
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
