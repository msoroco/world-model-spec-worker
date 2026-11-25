"""Publish reviewed original crest packets into the pinned Native capture layout."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from analysis import analyze


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()]


def bridge(root, original, *, assignment_id, case_id, release, expected_frames=900):
    root = Path(root).resolve()
    original = Path(original).resolve()
    require(original.parent == root and original.name == 'original',
            'original Native source must be canonical child')
    require(release.get('world_restored') and release.get('actors_released') and
            release.get('sensors_released') and not release.get('errors'),
            'Native owner release readback required')
    manifest = root / 'capture' / 'manifest.json'
    evidence = root / 'capture' / 'evidence.jsonl'
    graph = root / 'capture' / 'native' / 'frames.jsonl'
    require(all(path.is_file() for path in (manifest, evidence, graph)),
            'original Native graph/evidence source missing')
    graph_manifest = json.loads(manifest.read_text())
    bodies = rows(original / 'frames.jsonl')
    rays = rows(original / 'crest-rays.jsonl')
    mapping = json.loads((original / 'frame-map.json').read_text())
    graph_rows, evidence_rows = rows(graph), rows(evidence)
    require(graph_manifest.get('frames') == expected_frames and
            len(bodies) == len(rays) == len(graph_rows) == len(evidence_rows) == expected_frames,
            'original graph/body/ray frame count differs')
    require(mapping.get('frames') == [row['frame'] for row in bodies],
            'original camera/body frame map differs')
    for body, ray, graph_row, evidence_row in zip(bodies, rays, graph_rows, evidence_rows):
        frame = body['frame']
        require(ray.get('frame') == graph_row.get('frame') ==
                evidence_row.get('original_frame') == frame and
                evidence_row.get('replay_frame') == frame and
                abs(evidence_row.get('recording_time_s', -1) - body['timestamp_s']) < 1e-4,
                'original Native graph/body/ray frame join differs')
    source_hashes = json.loads((original / 'source-hashes.json').read_text())
    for name, digest in source_hashes.items():
        path = original / name
        require(path.is_file() and not path.is_symlink() and
                hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                'original sealed source differs: ' + name)
    for item in original.iterdir():
        if item.name == 'original-png':
            shutil.copytree(item, root / item.name, copy_function=os.link)
        elif item.is_file():
            target = root / item.name
            require(not target.exists(), 'canonical source destination exists: ' + item.name)
            os.link(item, target)
    report = analyze(root, assignment_id=assignment_id, case_id=case_id,
                     expected_frames=expected_frames)
    (root / 'acquisition-provenance.json').write_text(
        json.dumps({'provenance_kind': 'native', 'diagnostic_fixture': False},
                   sort_keys=True) + '\n')
    from worker_exchange.native_output import seal_capture
    seal = seal_capture(root, frames=expected_frames,
                        restoration={'restored': True,
                                     'owner_release_readback': release},
                        errors=[], encoder_exit_codes={name: 0 for name in
                                                       ('overview','approach','reference_corner','driver_reference')},
                        context={'source_record': 'reviewed_original_crest'})
    return {'frame_count': expected_frames, 'analysis': report,
            'capture_seal': seal, 'physical_acceptance_claimed': False}
