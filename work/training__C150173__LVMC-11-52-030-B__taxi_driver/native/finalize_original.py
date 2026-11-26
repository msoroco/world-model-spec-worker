"""Join reviewed original taxi yellow-zone sources without legal inference."""
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from yellow_plan import VIEWS, check

REVIEWS = ('taxicab-review.json', 'sign-review.json', 'passenger-purpose-review.json',
           'ordinary-rules-review.json')
SOURCES = ('yellow-zone-native.jsonl', 'observed-passenger-activity.jsonl',
           'video_frames.jsonl', 'trace.jsonl',
           'road.xodr', 'yellow-road.xodr', 'sign-authority-pending.json',
           *(view + '.mkv' for view in VIEWS), *REVIEWS)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def inspect(attempt, manifest_path, expected_source_kind='original_native'):
    attempt = Path(attempt).resolve()
    manifest_path = Path(manifest_path).resolve()
    if manifest_path.parent != attempt:
        raise ValueError('Source manifest must reside in original attempt')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('source_kind') != expected_source_kind:
        raise ValueError('Source kind differs')
    if expected_source_kind == 'original_native':
        seal_path = attempt / 'capture-seal.json'
        if not seal_path.is_file() or manifest.get('capture_seal_sha256') != sha(seal_path):
            raise ValueError('Original Native capture seal binding missing')
        seal = json.loads(seal_path.read_text())
        if (seal.get('provenance_kind') != 'native' or
                seal.get('diagnostic_fixture') is not False or
                seal.get('frames') != 600):
            raise ValueError('Original Native capture seal differs')
    declared = manifest.get('sha256')
    if not isinstance(declared, dict) or set(declared) != set(SOURCES):
        raise ValueError('Exact original source set required')
    for name in SOURCES:
        path = attempt / name
        if not path.is_file() or sha(path) != declared[name]:
            raise ValueError('Missing or changed original source: ' + name)
        if (expected_source_kind == 'original_native' and
                name in seal.get('sources', {}) and
                seal['sources'][name] != declared[name]):
            raise ValueError('Original capture seal source differs: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    check(config, (attempt / 'yellow-road.xodr').read_text())
    pending = json.loads((attempt / 'sign-authority-pending.json').read_text())
    if pending.get('legal_verdict') is not None:
        raise ValueError('Legal verdict may not be prefilled by capture')
    taxi = json.loads((attempt / 'taxicab-review.json').read_text())
    sign = json.loads((attempt / 'sign-review.json').read_text())
    purpose = json.loads((attempt / 'passenger-purpose-review.json').read_text())
    ordinary = json.loads((attempt / 'ordinary-rules-review.json').read_text())
    for name, review in zip(REVIEWS, (taxi, sign, purpose, ordinary)):
        if (review.get('source_kind') != expected_source_kind or
                not review.get('source_basis') or review.get('legal_verdict') is not None):
            raise ValueError('Independent source review missing: ' + name)
    if (taxi.get('observed_taxicab') is not True or
            sign.get('observed_curb_color') != 'yellow' or
            sign.get('posted_hours_start') != '09:00' or
            sign.get('posted_hours_end') != '17:00' or
            purpose.get('observed_purpose') != config['requested_purpose']):
        raise ValueError('Observed taxi, curb, sign or passenger purpose differs')
    native = read_rows(attempt / 'yellow-zone-native.jsonl')
    frames = read_rows(attempt / 'video_frames.jsonl')
    trace = read_rows(attempt / 'trace.jsonl')
    if not all(len(rows) == 600 for rows in (native, frames, trace)):
        raise ValueError('Full 600-frame original source join required')
    start = datetime.fromisoformat(config['civil_start_local'])
    active = stopped = body_in_yellow = 0
    for i, (n, f, t) in enumerate(zip(native, frames, trace)):
        frame = n.get('native_frame')
        expected_time = (i + 1) / 20
        if (n.get('video_frame') != i or f.get('video_frame') != i or
                f.get('carla_frame') != frame or t.get('frame') != frame or
                not isinstance(frame, int) or
                any(not math.isclose(row.get('time_s', -1), expected_time, abs_tol=1e-4)
                    for row in (n, f, t))):
            raise ValueError('Original Native frame/time join differs')
        camera_frames = f.get('camera_native_frames')
        if (not isinstance(camera_frames, dict) or set(camera_frames) != set(VIEWS) or
                any(value != frame for value in camera_frames.values()) or
                n.get('source_cameras') != camera_frames):
            raise ValueError('Four original source camera frames required')
        if (n.get('source_kind') != expected_source_kind or
                not isinstance(n.get('taxi_actor_id'), int) or
                not isinstance(n.get('passenger_proxy_id'), int)):
            raise ValueError('Original taxi/passenger identity missing')
        civil = datetime.fromisoformat(n['civil_time_local'])
        if civil != start + timedelta(seconds=expected_time):
            raise ValueError('Original civil time join differs')
        velocity = n.get('taxi_velocity_xyz_mps')
        if not isinstance(velocity, list) or len(velocity) != 3 or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in velocity):
            raise ValueError('Observed taxi velocity missing')
        parked = sum(value * value for value in velocity) ** .5 <= .1
        vertices = n.get('taxi_body_vertices_xyz_m')
        if (not isinstance(vertices, list) or len(vertices) != 8 or
                any(not isinstance(v, list) or len(v) != 3 or
                    any(type(coord) not in (int, float) or not math.isfinite(coord)
                        for coord in v) for v in vertices)):
            raise ValueError('Original taxi body footprint missing')
        inside = all(3.5 <= v[0] <= 7 and 5 <= v[1] <= 25 for v in vertices)
        body_in_yellow += parked and inside
        stopped += parked
        active += parked and inside and '09:00' <= civil.strftime('%H:%M') < '17:00'
    return {'format': 'c150173-source-joined-yellow-zone-measurement-v1',
            'case_id': config['case_id'], 'frames': 600, 'stopped_frames': stopped,
            'yellow_zone_body_frames': body_in_yellow,
            'posted_active_stopped_frames': active,
            'observed_purpose': purpose['observed_purpose'],
            'taxicab_identity_reviewed': expected_source_kind == 'original_native',
            'sign_source_reviewed': expected_source_kind == 'original_native',
            'outside_hours_ordinary_rules_status': ordinary.get('review_status', 'unresolved'),
            'source_manifest_sha256': sha(manifest_path),
            'source_kind': expected_source_kind,
            'original_native_observed': expected_source_kind == 'original_native',
            'legal_verdict': None}


def finalize(attempt, manifest_path, output):
    result = inspect(attempt, manifest_path, 'original_native')
    output = Path(output)
    if output.exists():
        raise ValueError('Fresh measurement output required')
    output.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt,
                              Path(args.attempt) / 'source-manifest.json',
                              args.output), sort_keys=True))
