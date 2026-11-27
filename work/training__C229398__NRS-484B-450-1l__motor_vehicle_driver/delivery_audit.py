"""Independent source and saved-output acceptance for NRS 484B.450(1)(l)."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ('road.xodr', 'map-geometry.json', 'vehicle-poses.jsonl',
           'body-footprints.jsonl', 'video_frames.jsonl', 'highway-review.json',
           'activity-review.json', 'exception-review.json', 'pixel-review.json',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic, omit_source=None):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((row for row in manifest['cases'] if row['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    selected = entry if candidate == 'primary' else next(
        (row for row in entry['candidates'] if row['id'] == candidate), None)
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
    for name in SOURCES:
        if name == omit_source:
            raise ValueError('Missing source: ' + name)
        source = stage / name
        if not source.is_file():
            raise ValueError('Missing source: ' + name)
        hashes[name] = digest(source)
        if saved.get('original_source_hashes', {}).get(name) != hashes[name]:
            raise ValueError('Saved original source changed: ' + name)
    result = read(stage / 'result.json')
    report = read(stage / 'analysis-report.json')
    if (result.get('case_id') != case or result.get('trace_reference') != 'trace.jsonl' or
            len((stage / 'trace.jsonl').read_text().splitlines()) != 600 or
            any(len((stage / name).read_text().splitlines()) != 600 for name in
                ('vehicle-poses.jsonl', 'body-footprints.jsonl', 'video_frames.jsonl'))):
        raise ValueError('Original two-vehicle trace or frame map differs')
    for key in ('highway_side_place', 'stop_mode', 'stand_mode', 'park_mode',
                'traffic_conflict_necessity', 'compliance_with_law',
                'police_direction', 'device_direction'):
        measurement = report.get('measurements', {}).get(key, {})
        if any(measurement.get('sources', {}).get(name) != value for name, value in hashes.items()):
            raise ValueError('Source-bound measurement differs: ' + key)
    overlap = report['measurements']['highway_side_place']['value']['concurrent_overlap_at_rest_frame_count']
    if type(overlap) is not int or overlap < 0:
        raise ValueError('Two-vehicle overlap measurement differs')
    geometry = read(stage / 'map-geometry.json')
    highway = read(stage / 'highway-review.json')
    activity = read(stage / 'activity-review.json')
    exception = read(stage / 'exception-review.json')
    pixel = read(stage / 'pixel-review.json')
    if (geometry.get('cell_id') != 'C229398' or
            highway.get('road_sha256') != hashes['road.xodr'] or
            highway.get('map_sha256') != hashes['map-geometry.json'] or
            activity.get('body_sha256') != hashes['body-footprints.jsonl'] or
            exception.get('body_sha256') != hashes['body-footprints.jsonl'] or
            len({row.get('source') for row in (highway, activity, exception, pixel)}) != 4):
        raise ValueError('Independent curb, activity, exception or pixel source join differs')
    if diagnostic:
        receipt = read(Path(attempt) / 'compatibility.json')
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('candidate_id') != candidate or
                receipt.get('construction_sha256') != selected['construction_sha256'] or
                not (stage / 'fixture-provenance.json').is_file()):
            raise ValueError('Diagnostic compatibility identity differs')
    else:
        provenance = read(Path(attempt) / 'acquisition-provenance.json')
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native acquisition required')
        for review in (highway, activity, exception, pixel):
            if review.get('review_status') != 'independently_reviewed' or not review.get('reviewer'):
                raise ValueError('Independent original review incomplete')
        if (not highway.get('highway_authority_source') or not highway.get('curb_authority_source') or
                not activity.get('purpose_source') or
                any(not exception.get(key) for key in ('traffic_conflict_source',
                    'law_compliance_source', 'police_direction_source', 'device_direction_source')) or
                pixel.get('overview_sha256') != hashes['overview.mkv'] or
                pixel.get('actual_pixels_verified') is not True):
            raise ValueError('Original highway, activity, exception or actual pixels unresolved')
        if (result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met' or
                result.get('maneuver_completed') is not True):
            raise ValueError('Original physical approach completion unverified')
    return {'format': 'c229398-independent-delivery-audit-v1', 'case_id': case,
            'candidate_id': candidate, 'construction_sha256': selected['construction_sha256'],
            'saved_processing_sha256': digest(processing), 'source_sha256': hashes,
            'concurrent_overlap_at_rest_frame_count': overlap,
            'diagnostic_only': diagnostic, 'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source', choices=SOURCES)
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
