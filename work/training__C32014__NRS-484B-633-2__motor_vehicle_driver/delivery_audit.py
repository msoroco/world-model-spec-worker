"""Independent source-bound bridge speed delivery review.

The CPU diagnostic path tests joins and rejection. Only original Native evidence,
an independently sourced Department determination, and pixel review can advance
the physical audit. Neither path declares a legal verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ('bridge-speed-history.jsonl', 'bridge-context.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr', 'overview.mkv',
           'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    if not path.is_file():
        raise ValueError('Missing original delivery source: ' + path.name)
    return json.loads(path.read_text())


def rows(path):
    if not path.is_file():
        raise ValueError('Missing original delivery source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_authority(path, context, road_sha256=None):
    """Require a document-backed administrative fact outside authored OpenDRIVE."""
    authority = read(path)
    source = authority.get('department_source', {})
    if (authority.get('issuing_body') != 'Nevada Department of Transportation'
            or authority.get('review_status') != 'independently_verified'
            or not source.get('path') or not source.get('sha256')
            or not source.get('record_id') or not source.get('verification_method')
            or authority.get('declared_maximum_mph') != context.get('sign_limit_mph')
            or not authority.get('bridge_identifier')
            or (road_sha256 is not None and
                authority.get('structure_geometry_sha256') != road_sha256)):
        raise ValueError('Department structural maximum source invalid or unverified')
    document = Path(source['path']).resolve()
    if not document.is_file() or sha(document) != source['sha256']:
        raise ValueError('Department structural maximum document missing or stale')
    return authority


def audit(case, processing, diagnostic=False, omit_source=None):
    manifest = read(ROOT / 'execution-manifest.json')
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact bridge-speed delivery case')
    saved = read(Path(processing))
    if (saved.get('case_id') != case or saved.get('passed') is not True
            or saved.get('recorded_only') is not True or saved.get('originals_preserved') is not True
            or saved.get('candidate_id') != 'primary'
            or saved.get('native_revision', {}).get('construction_sha256') != entry['construction_sha256']
            or saved.get('timestamp_joins', {}).get('frames') != 600
            or saved.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Saved processing or complete decode differs')
    stage = Path(saved['analysis_directory'])
    hashes = {}
    for name in SOURCES:
        if name == omit_source:
            raise ValueError('Missing original delivery source: ' + name)
        path = stage / name
        if not path.is_file():
            raise ValueError('Missing original delivery source: ' + name)
        hashes[name] = sha(path)
        if saved.get('original_source_hashes', {}).get(name) != hashes[name]:
            raise ValueError('Original source hash differs: ' + name)
    result = read(stage / 'result.json')
    report = read(stage / 'analysis-report.json')
    history = rows(stage / 'bridge-speed-history.jsonl')
    mapping = rows(stage / 'video_frames.jsonl')
    trace = rows(stage / 'trace.jsonl')
    evidence = rows(stage / 'capture/evidence.jsonl')
    if (result.get('case_id') != case or len(history) != 600 or len(mapping) != 600
            or len(trace) != 600 or len(evidence) != 600):
        raise ValueError('Original bridge measurement or full-frame evidence incomplete')
    for i, (movement, frame, state) in enumerate(zip(history, mapping, trace)):
        if (movement.get('video_frame') != i or frame.get('video_frame') != i
                or movement.get('native_frame') != frame.get('native_frame')
                or state.get('frame') != frame.get('carla_frame')
                or abs(movement['time_s'] - frame['time_s']) > 1e-6
                or abs(state['time_s'] - frame['time_s']) > 1e-6):
            raise ValueError('Original bridge frame/time join differs')
    measurement = report.get('measurements', {}).get('bridge_speed_observation', {})
    if (measurement.get('method') != 'measure_bridge'
            or any(measurement.get('sources', {}).get(name) != hashes[name]
                   for name in ('bridge-speed-history.jsonl', 'bridge-context.json',
                                'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr'))):
        raise ValueError('Original bridge speed measurement binding differs')
    context = read(stage / 'bridge-context.json')
    observed = measurement.get('value', {})
    if (observed.get('frames') != 600 or observed.get('on_structure_frames', 0) <= 0
            or observed.get('posted_maximum_mph') != context.get('sign_limit_mph')
            or observed.get('legal_conclusion') is not None):
        raise ValueError('Bridge occupancy or legal uncertainty differs')
    if diagnostic:
        if result.get('provenance_kind') not in ('synthetic_fixture', 'synthetic_local_diagnostic'):
            raise ValueError('CPU proof may use only synthetic diagnostic provenance')
    else:
        provenance = read(stage / 'acquisition-provenance.json')
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native source provenance incomplete')
        check_authority(stage / 'department-determination.json', context, hashes['road.xodr'])
        pixels = read(stage / 'pixel-review.json')
        if (pixels.get('review_status') != 'independently_reviewed'
                or pixels.get('bridge_mesh_visible') is not True
                or pixels.get('both_sign_faces_legible') is not True
                or pixels.get('video_frame_map_sha256') != hashes['video_frames.jsonl']
                or pixels.get('bridge_context_sha256') != hashes['bridge-context.json']):
            raise ValueError('Original bridge/sign pixels lack independent review')
        if result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
            raise ValueError('Original bridge traversal completion unverified')
    return {'format': 'worker-bridge-speed-delivery-audit', 'case_id': case,
            'processing_sha256': sha(processing), 'source_sha256': hashes,
            'diagnostic_only': diagnostic, 'authority_verified': not diagnostic,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source', choices=SOURCES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError('Diagnostic omission only')
    args.output.write_text(json.dumps(audit(args.case, args.processing, args.diagnostic,
                                           args.omit_source), indent=2) + '\n')
