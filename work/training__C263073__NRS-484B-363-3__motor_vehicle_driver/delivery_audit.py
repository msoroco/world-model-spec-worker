"""Independent saved-source audit for exact school-zone U-turn attempts."""
import argparse
import hashlib
import json
from pathlib import Path

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
