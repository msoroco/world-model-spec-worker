"""Independently inspect an original taxi/light-express freight capture."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from audit_original import VIEWS, decode


SOURCES = ('freight-native.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'road.xodr', 'yellow-freight-road.xodr',
           'sign-authority-pending.json', 'commercial-status-review.json',
           'sign-review.json', 'freight-purpose-review.json',
           *(name + '.mkv' for name in VIEWS))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(attempt):
    attempt = Path(attempt).resolve()
    source_path, seal_path = attempt / 'source-manifest.json', attempt / 'capture-seal.json'
    if not source_path.is_file() or not seal_path.is_file():
        raise ValueError('Original freight source seal or review manifest missing')
    source, seal = json.loads(source_path.read_text()), json.loads(seal_path.read_text())
    if (source.get('source_kind') != 'original_native' or
            source.get('capture_seal_sha256') != sha(seal_path) or
            seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not False or seal.get('frames') != 600):
        raise ValueError('Original freight Native seal binding differs')
    bound = source.get('sha256', {})
    if not isinstance(bound, dict) or set(bound) != set(SOURCES):
        raise ValueError('Exact original freight source set required')
    for name in SOURCES:
        path = attempt / name
        if not path.is_file() or sha(path) != bound[name]:
            raise ValueError('Original freight source missing or changed: ' + name)
        prior = seal.get('sources', {}).get(name)
        if prior is not None and prior != bound[name]:
            raise ValueError('Original freight captured source changed: ' + name)
    reviews = {name: json.loads((attempt / name).read_text()) for name in
               ('commercial-status-review.json', 'sign-review.json',
                'freight-purpose-review.json')}
    required = {
        'commercial-status-review.json': {'freight-native.jsonl', 'overview.mkv'},
        'sign-review.json': {'yellow-freight-road.xodr', 'reference_corner.mkv'},
        'freight-purpose-review.json': {'freight-native.jsonl', 'approach.mkv'}}
    for name, review in reviews.items():
        refs = review.get('source_refs')
        if (review.get('source_kind') != 'original_native' or
                not review.get('source_basis') or review.get('legal_verdict') is not None or
                not isinstance(refs, dict) or not required[name] <= set(refs) or
                any(bound.get(source) != digest for source, digest in refs.items())):
            raise ValueError('Original freight review lacks independent source: ' + name)
    native, mapping, trace = [rows(attempt / name) for name in
                              ('freight-native.jsonl', 'video_frames.jsonl', 'trace.jsonl')]
    if any(len(group) != 600 for group in (native, mapping, trace)):
        raise ValueError('Full 600-frame original freight join required')
    taxi, cargo = native[0].get('taxi_actor_id'), native[0].get('cargo_actor_id')
    if (type(taxi) is not int or type(cargo) is not int or taxi == cargo or
            reviews['commercial-status-review.json'].get('taxi_actor_id') != taxi or
            reviews['freight-purpose-review.json'].get('cargo_actor_id') != cargo):
        raise ValueError('Original taxi/cargo/review actor identity differs')
    centres = []
    for index, (n, m, t) in enumerate(zip(native, mapping, trace)):
        frame = n.get('native_frame')
        time_s = (index + 1) / 20
        if (n.get('source_kind') != 'original_native' or
                n.get('video_frame') != index or m.get('video_frame') != index or
                m.get('carla_frame') != frame or t.get('frame') != frame or
                type(frame) is not int or n.get('taxi_actor_id') != taxi or
                n.get('cargo_actor_id') != cargo or
                any(not math.isclose(row.get('time_s', -1), time_s, abs_tol=1e-4)
                    for row in (n, m, t)) or
                m.get('camera_native_frames') != {view: frame for view in VIEWS} or
                n.get('source_cameras') != m.get('camera_native_frames') or
                (index and frame <= native[index-1].get('native_frame', -1))):
            raise ValueError('Original freight Native/frame/camera join differs')
        for key in ('taxi_body_vertices_xyz_m', 'cargo_body_vertices_xyz_m'):
            vertices = n.get(key)
            if (not isinstance(vertices, list) or len(vertices) != 8 or
                    any(not isinstance(v, list) or len(v) != 3 or
                        any(type(x) not in (int, float) or not math.isfinite(x)
                            for x in v) for v in vertices)):
                raise ValueError('Original freight body geometry missing: ' + key)
        centres.append(tuple(sum(v[j] for v in n['cargo_body_vertices_xyz_m']) / 8
                             for j in range(3)))
    videos = {view: decode(attempt / (view + '.mkv'), dimensions)
              for view, dimensions in VIEWS.items()}
    return {'format': 'c150173-independent-original-freight-audit-v1',
            'frames': 600, 'source_manifest_sha256': sha(source_path),
            'capture_seal_sha256': sha(seal_path), 'videos': videos,
            'taxi_actor_id': taxi, 'cargo_actor_id': cargo,
            'cargo_displacement_m': math.dist(centres[0], centres[-1]),
            'commercial_classification_reviewed': True,
            'commercial_classification_conclusion': reviews['commercial-status-review.json'].get('observed_commercial_use'),
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    report = audit(args.attempt)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
