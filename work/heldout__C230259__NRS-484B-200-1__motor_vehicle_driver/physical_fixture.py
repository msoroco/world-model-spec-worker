"""Source-joined synthetic physical outcome and lifecycle CPU fixtures."""

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
KINDS = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
         'missing_evidence': 'unverified'}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def evaluate(case, kind):
    if kind not in KINDS:
        raise ValueError('Unknown synthetic physical outcome')
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entries = [entry for entry in manifest['cases'] if entry['case_id'] == case]
    if len(entries) != 1:
        raise ValueError('Unknown exact case')
    suffix = case.rsplit('__', 1)[-1]
    diagnostic = HERE / ('diagnostic-' + suffix + '.json')
    source = json.loads(diagnostic.read_text())
    delivery = HERE / (suffix.replace('_', '-') + '-delivery-proof.json')
    audit = json.loads(delivery.read_text())
    compatibility = HERE / entries[0]['compatibility']['receipt']
    receipt = json.loads(compatibility.read_text())
    if digest(compatibility) != entries[0]['compatibility']['sha256'] or not receipt['passed']:
        raise ValueError('Current exact compatibility receipt differs')
    if audit['case_id'] != case or not all(audit.get(key) for key in
            ('originals_joined', 'analysis_recomputed', 'four_camera_full_decode')):
        raise ValueError('Independent original source audit differs')
    for name, expected in audit['source_sha256'].items():
        if name not in source['files'] or sha256(source['files'][name].encode()).hexdigest() != expected:
            raise ValueError('Diagnostic original source differs: ' + name)
        if receipt['fixture_manifest'].get(name) != expected:
            raise ValueError('Current compatibility original differs: ' + name)
    road = rows(source['files']['ego_road_frames.jsonl'])
    trace = rows(source['files']['trace.jsonl'])
    frames = rows(source['files']['video_frames.jsonl'])
    if not road or len(road) != len(trace) or len(road) != len(frames):
        raise ValueError('Original source frame counts differ')
    for index, (body, motion, frame) in enumerate(zip(road, trace, frames)):
        identity = body['frame'], body['time_s']
        if (motion['frame'], motion['time_s']) != identity or (
                frame['carla_frame'], frame['time_s']) != identity or frame['video_frame'] != index:
            raise ValueError('Original road, motion and video frame join differs')
    distance = sum(math.dist(a['position_m'], b['position_m'])
                   for a, b in zip(trace, trace[1:]))
    if distance <= 0:
        raise ValueError('Diagnostic route made no progress')
    status = KINDS[kind]
    return {'case_id': case, 'fixture_kind': kind, 'fixture_only': True,
            'diagnostic_fixture': True, 'actual_native_capture': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'source-hashed original road, trace and frame join with explicit synthetic outcome',
                'sources': {'diagnostic': diagnostic.name,
                            'diagnostic_sha256': digest(diagnostic),
                            'original_source_audit': delivery.name,
                            'original_source_audit_sha256': digest(delivery),
                            'compatibility_receipt_sha256': digest(compatibility),
                            'fixture_mutation': kind},
                'missing_evidence': ['ego_road_frames.jsonl'] if kind == 'missing_evidence' else []}},
            'maneuver_completed': status == 'met',
            'realized_observables': {'diagnostic_route_progress_m': distance,
                                     'diagnostic_source_frames': len(frames)} if status == 'met' else {},
            'provenance_kind': 'synthetic_fixture',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def lifecycle(out_of_order=False):
    if out_of_order:
        raise ValueError('Saved processing precedes Native owner release')
    return {'events': EVENTS, 'fixture_only': True,
            'native_capture_claimed': False, 'saved_processing_after_owner_release': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=sorted(KINDS))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--lifecycle', action='store_true')
    parser.add_argument('--out-of-order', action='store_true')
    args = parser.parse_args()
    result = lifecycle(args.out_of_order) if args.lifecycle else evaluate(args.case, args.kind)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
