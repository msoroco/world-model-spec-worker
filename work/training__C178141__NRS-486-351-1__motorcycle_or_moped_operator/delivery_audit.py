"""Independent original-source audit for selected adjacent-vehicle cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_NAMES = ('road.xodr', 'lane-inventory.json', 'split-review.json',
                'classification-review.json', 'duty-review.json',
                'actor-poses.jsonl', 'video_frames.jsonl', 'overview.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic, omit_source=None):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    selected = entry if candidate == 'primary' else next(
        (e for e in entry['candidates'] if e['id'] == candidate), None)
    if selected is None:
        raise ValueError('Unknown selected candidate')
    saved = read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != case or saved.get('candidate_id') != candidate or
            saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Selected saved processing or full-frame decode differs')
    stage = Path(saved['analysis_directory']).resolve()
    hashes = {}
    for name in SOURCE_NAMES:
        if name == omit_source:
            raise ValueError('Missing source: ' + name)
        source = stage / name
        if not source.is_file():
            raise ValueError('Missing source: ' + name)
        hashes[name] = sha(source)
    result = read(stage / 'result.json')
    report = read(stage / 'analysis-report.json')
    if (result.get('case_id') != case or result.get('trace_reference') != 'trace.jsonl' or
            len((stage / 'trace.jsonl').read_text().splitlines()) != 600 or
            len((stage / 'video_frames.jsonl').read_text().splitlines()) != 600):
        raise ValueError('Original trace or frame map differs')
    contract = read(HERE / entry['measurement_contract'])
    for row in contract['requirements']:
        measurement = report.get('measurements', {}).get(row['output_key'], {})
        if measurement.get('method') != row['method'] or any(
                measurement.get('sources', {}).get(name) != hashes[name] for name in SOURCE_NAMES):
            raise ValueError('Source-bound adjacent-vehicle measurement differs: ' + row['output_key'])
    value = result.get('measured_values', {})
    if (type(value.get('between_vehicle_frames')) is not int or
            not isinstance(value.get('between_vehicle_intervals'), list) or
            len(value.get('left_vehicle_speed_mps_range', [])) != 2 or
            len(value.get('right_vehicle_speed_mps_range', [])) != 2):
        raise ValueError('Adjacent-vehicle body and velocity measurement differs')
    split = read(stage / 'split-review.json')
    classification = read(stage / 'classification-review.json')
    duty = read(stage / 'duty-review.json')
    if (split.get('road_sha256') != hashes['road.xodr'] or
            split.get('pose_sha256') != hashes['actor-poses.jsonl'] or
            classification.get('pose_sha256') != hashes['actor-poses.jsonl'] or
            duty.get('pose_sha256') != hashes['actor-poses.jsonl'] or
            len({split.get('source'), classification.get('source'), duty.get('source')}) != 3 or
            duty.get('officer_identity_source') == duty.get('performance_of_duty_source')):
        raise ValueError('Independent lane, classification or duty source join differs')
    if diagnostic:
        receipt = read(Path(attempt) / 'compatibility.json')
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('candidate_id') != candidate or
                receipt.get('construction_sha256') != selected['construction_sha256']):
            raise ValueError('Diagnostic compatibility identity differs')
    else:
        provenance = read(Path(attempt) / 'acquisition-provenance.json')
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native acquisition required')
        for review in (split, classification, duty):
            if review.get('review_status') != 'independently_reviewed' or not review.get('reviewer'):
                raise ValueError('Independent original review incomplete')
        if split.get('overview_sha256') != hashes['overview.mkv']:
            raise ValueError('Original adjacent-lane pixels differ')
        if not classification.get('chapter_definition_source') or not duty.get('officer_identity_source') or not duty.get('performance_of_duty_source'):
            raise ValueError('Original machine classification or police-duty source unresolved')
        physical = result.get('physical_checks', {}).get('maneuver', {})
        if physical.get('status') != 'met' or result.get('maneuver_completed') is not True:
            raise ValueError('Original motorcycle passage completion unverified')
    return {'format': 'c178141-independent-delivery-audit-v1', 'case_id': case,
            'candidate_id': candidate, 'construction_sha256': selected['construction_sha256'],
            'saved_processing_sha256': sha(processing), 'original_source_sha256': hashes,
            'diagnostic_only': diagnostic, 'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source', choices=SOURCE_NAMES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError('Source omission is diagnostic only')
    receipt = audit(args.case, args.candidate, args.attempt, args.processing,
                    args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError('Retain previous delivery audit result')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
