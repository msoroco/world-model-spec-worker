"""Independent original-source audit for selected access-aisle deliveries."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_NAMES = ('road.xodr', 'aisle-context.json', 'premises-review.json',
                'aisle-designation-review.json', 'parking-review.json',
                'native-vehicle.jsonl', 'video_frames.jsonl', 'reference_corner.mkv')


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
        path = stage / name
        if not path.is_file():
            raise ValueError('Missing source: ' + name)
        hashes[name] = sha(path)
    result = read(stage / 'result.json')
    report = read(stage / 'analysis-report.json')
    if (result.get('case_id') != case or result.get('trace_reference') != 'trace.jsonl' or
            len((stage / 'trace.jsonl').read_text().splitlines()) != 600 or
            len((stage / 'video_frames.jsonl').read_text().splitlines()) != 600):
        raise ValueError('Original trace or frame map differs')
    measurement = report.get('measurements', {}).get('source_bound_aisle_parking', {})
    if (measurement.get('method') != 'measured' or
            any(measurement.get('sources', {}).get(name) != hashes[name] for name in SOURCE_NAMES)):
        raise ValueError('Source-bound aisle measurement differs')
    value = measurement.get('value', {})
    if (value.get('frame_count') != 600 or value.get('legal_verdict_claimed') is not False or
            type(value.get('stationary_overlap_samples')) is not int):
        raise ValueError('Aisle footprint measurement differs')
    designation = read(stage / 'aisle-designation-review.json')
    premises = read(stage / 'premises-review.json')
    parking = read(stage / 'parking-review.json')
    if (designation.get('road_sha256') != hashes['road.xodr'] or
            premises.get('road_sha256') != hashes['road.xodr'] or
            designation.get('pixel_sha256') != hashes['reference_corner.mkv'] or
            parking.get('motion_sha256') != hashes['native-vehicle.jsonl'] or
            len({designation.get('source'), premises.get('source'), parking.get('source')}) != 3 or
            not designation.get('contrasting_marking_or_paving') or
            designation.get('vehicle_ingress_egress') is not True or
            designation.get('accessible_route_connectivity') is not True or
            not designation.get('adjacent_accessible_bay') or
            premises.get('jurisdiction_reviewed') is not True or
            parking.get('vehicle_class') != 'motor_vehicle' or
            not parking.get('responsible_person') or
            any(not parking.get(k) for k in ('occupancy', 'loading_purpose', 'actual_loading_activity'))):
        raise ValueError('Independent premises, designation, route or parking source join differs')
    if designation.get('designation_route') == '11.52.135(A)_sign':
        sign = designation.get('conditional_11_52_135A_sign')
        if not isinstance(sign, dict) or sign.get('access_symbol') is not True or not sign.get('minimum_fine_wording_or_equivalent') or type(sign.get('sign_bottom_height_ft')) not in (int, float) or sign['sign_bottom_height_ft'] < 4:
            raise ValueError('Conditional accessible-space sign source incomplete')
    elif designation.get('designation_route') != 'direct_marking_and_accessible_bay':
        raise ValueError('Aisle designation route differs')
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
        for source in (designation, premises, parking):
            if source.get('review_status') != 'independently_reviewed' or not source.get('reviewer'):
                raise ValueError('Independent original review incomplete')
        pixel = read(stage / 'aisle-pixel-review.json')
        if (pixel.get('review_status') != 'independently_reviewed' or
                pixel.get('frame_map_sha256') != hashes['video_frames.jsonl'] or
                pixel.get('source_video_sha256') != hashes['reference_corner.mkv']):
            raise ValueError('Independent original aisle pixel review incomplete')
        physical = result.get('physical_checks', {}).get('maneuver', {})
        if physical.get('status') != 'met' or result.get('maneuver_completed') is not True:
            raise ValueError('Original physical approach completion unverified')
    return {'format': 'c200542-independent-delivery-audit-v1', 'case_id': case,
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
    print(json.dumps({'passed': True, 'case_id': args.case,
                      'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
