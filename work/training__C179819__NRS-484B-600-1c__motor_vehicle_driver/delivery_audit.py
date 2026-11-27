"""Independent saved-source delivery check for the absolute 80 mph branch."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_NAMES = ('native_motion.jsonl', 'road_context.json', 'video_frames.jsonl',
                'trace.jsonl', 'road.xodr', 'overview.mkv', 'approach.mkv',
                'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: '+path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic=False, omit_source=None):
    manifest = read(HERE/'execution-manifest.json')
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown selected speed case')
    selected = entry if candidate == 'primary' else next((c for c in entry['candidates'] if c['id'] == candidate), None)
    if selected is None:
        raise ValueError('Unknown selected speed candidate')
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
            raise ValueError('Missing source: '+name)
        path = stage/name
        if not path.is_file():
            raise ValueError('Missing source: '+name)
        hashes[name] = sha(path)
    result = read(stage/'result.json')
    analysis = read(stage/'analysis-report.json')
    context = read(stage/'road_context.json')
    if (result.get('case_id') != case or context.get('case_id') != case or
            result.get('trace_reference') != 'trace.jsonl' or
            len((stage/'trace.jsonl').read_text().splitlines()) != 600 or
            len((stage/'video_frames.jsonl').read_text().splitlines()) != 600):
        raise ValueError('Exact original trace, context or frame map differs')
    sources = analysis.get('measurements', {}).get('speed_observation', {}).get('sources', {})
    if any(sources.get(name) != hashes[name] for name in
           ('native_motion.jsonl', 'road_context.json', 'video_frames.jsonl', 'trace.jsonl', 'road.xodr')):
        raise ValueError('Source-bound original speed measurement differs')
    value = analysis['measurements']['speed_observation']['value']
    if (value.get('statutory_cap_mph') != 80.0 or value.get('sample_count') != 600 or
            value.get('posted_limit_required') is not False or
            value.get('legal_verdict_claimed') is not False):
        raise ValueError('Absolute speed measurement or no-posting context differs')
    if diagnostic:
        receipt = read(Path(attempt)/'compatibility.json')
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('candidate_id') != candidate or
                receipt.get('construction_sha256') != selected['construction_sha256'] or
                context.get('review_kind') != 'synthetic_diagnostic'):
            raise ValueError('Synthetic diagnostic identity differs')
    else:
        provenance = read(Path(attempt)/'acquisition-provenance.json')
        if (provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True or
                context.get('review_kind') != 'original_source_review' or not context.get('reviewer') or
                context.get('camera_sha256') != {name: hashes[name] for name in SOURCE_NAMES if name.endswith('.mkv')}):
            raise ValueError('Original Native velocity, identity or camera review incomplete')
        pixels = read(stage/'pixel-review.json')
        if (pixels.get('review_status') != 'independently_reviewed' or not pixels.get('reviewer') or
                pixels.get('frame_map_sha256') != hashes['video_frames.jsonl'] or
                pixels.get('source_video_sha256') != hashes['driver_reference.mkv'] or
                pixels.get('ego_visible') is not True or pixels.get('other_vehicle_visible') is not True):
            raise ValueError('Original source pixels lack independent participant review')
        if (result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met' or
                result.get('maneuver_completed') is not True):
            raise ValueError('Original physical travel completion unverified')
    return {'format': 'worker-absolute-speed-delivery-audit', 'case_id': case,
            'candidate_id': candidate, 'construction_sha256': selected['construction_sha256'],
            'saved_processing_sha256': sha(processing), 'source_sha256': hashes,
            'diagnostic_only': diagnostic, 'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
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
        raise ValueError('Diagnostic source omission only')
    receipt = audit(args.case, args.candidate, args.attempt, args.processing,
                    args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError('Retain prior delivery audit result')
    args.output.write_text(json.dumps(receipt, indent=2)+'\n')
