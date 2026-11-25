"""Independent taxi first-turn saved-source review gate."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_NAMES = ('road.xodr', 'route-survey.json', 'actor-poses.jsonl',
                'video_frames.jsonl', 'trace.jsonl', 'reference_corner.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(case, attempt, processing, diagnostic, omit_source):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((row for row in manifest['cases'] if row['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown selected taxi case')
    saved = read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != case or saved.get('candidate_id') != 'primary' or
            saved.get('native_revision', {}).get('construction_sha256') != entry['construction_sha256'] or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Selected saved processing or full-frame decode differs')
    stage = Path(saved['analysis_directory']).resolve()
    hashes = {}
    for name in SOURCE_NAMES:
        if name == omit_source or not (stage / name).is_file():
            raise ValueError('Missing source: ' + name)
        hashes[name] = sha(stage / name)
    result = read(stage / 'result.json')
    analysis = read(stage / 'analysis-report.json')
    if (result.get('case_id') != case or result.get('trace_reference') != 'trace.jsonl' or
            len((stage / 'trace.jsonl').read_text().splitlines()) != 600 or
            len((stage / 'video_frames.jsonl').read_text().splitlines()) != 600):
        raise ValueError('Original trace or frame map differs')
    measurement = analysis.get('measurements', {}).get('source_bound_first_turn', {})
    if (measurement.get('method') != 'first_turn_measurement' or
            any(measurement.get('sources', {}).get(name) != hashes[name] for name in SOURCE_NAMES)):
        raise ValueError('Source-bound first-turn measurement differs')
    expected = 'right' if case.endswith('probe_01') else 'straight'
    value = measurement.get('value', {})
    if (value.get('requested_first_turn') != expected or
            value.get('observed_first_turn') != expected or
            value.get('sampled_path_m', 0) < 100):
        raise ValueError('First-junction source measurement differs')
    survey = read(stage / 'route-survey.json')
    if survey.get('road_sha256') != hashes['road.xodr']:
        raise ValueError('Route survey does not bind retained road')
    if diagnostic:
        fixture = read(Path(attempt) / 'compatibility.json')
        if (fixture.get('passed') is not True or fixture.get('case_id') != case or
                fixture.get('construction_sha256') != entry['construction_sha256']):
            raise ValueError('Diagnostic compatibility identity differs')
    else:
        provenance = read(Path(attempt) / 'acquisition-provenance.json')
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native acquisition required')
        if (survey.get('review_status') != 'independently_reviewed' or
                not survey.get('reviewer') or survey.get('synthetic_diagnostic') is True):
            raise ValueError('Independent route and authority review incomplete')
        pixels = read(stage / 'sign-pixel-review.json')
        if (pixels.get('review_status') != 'independently_reviewed' or
                not pixels.get('reviewer') or pixels.get('frame_map_sha256') != hashes['video_frames.jsonl'] or
                pixels.get('source_video_sha256') != hashes['reference_corner.mkv']):
            raise ValueError('Independent original notice pixel review incomplete')
        physical = result.get('physical_checks', {}).get('maneuver', {})
        if physical.get('status') != 'met' or result.get('maneuver_completed') is not True:
            raise ValueError('Original physical maneuver completion unverified')
    return {'format': 'c110875-independent-delivery-audit-v1', 'case_id': case,
            'construction_sha256': entry['construction_sha256'],
            'saved_processing_sha256': sha(processing), 'original_source_sha256': hashes,
            'diagnostic_only': diagnostic, 'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source', choices=SOURCE_NAMES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError('Source omission is diagnostic only')
    receipt = audit(args.case, args.attempt, args.processing, args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError('Retain previous delivery audit result')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
