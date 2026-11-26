"""Publish sealed original rail packets into the pinned Native layout."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from analysis import analyze


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def bridge(root, original, *, assignment_id, case_id, release, expected_frames=900):
    root, original = Path(root).resolve(), Path(original).resolve()
    if original.parent != root or original.name != 'original':
        raise ValueError('original railroad source must be canonical child')
    if not all(release.get(key) for key in ('world_restored', 'actors_released',
                                            'sensors_released', 'encoders_closed')) or release.get('errors'):
        raise ValueError('Native railroad owner release readback required')
    manifest = root / 'capture' / 'manifest.json'
    evidence = root / 'capture' / 'evidence.jsonl'
    graph = root / 'capture' / 'native' / 'frames.jsonl'
    if not all(path.is_file() for path in (manifest, evidence, graph)):
        raise ValueError('original Native rail graph/evidence source missing')
    graph_manifest = json.loads(manifest.read_text())
    body, graph_rows, evidence_rows = (rows(path) for path in (
        original / 'rail-frames.jsonl', graph, evidence))
    if graph_manifest.get('frames') != expected_frames or any(
            len(group) != expected_frames for group in (body, graph_rows, evidence_rows)):
        raise ValueError('original rail graph/body/evidence frame count differs')
    for body_row, graph_row, evidence_row in zip(body, graph_rows, evidence_rows):
        frame = body_row['original_frame']
        if (graph_row.get('frame') != evidence_row.get('original_frame') or
                evidence_row.get('replay_frame') != frame or graph_row.get('frame') != frame or
                abs(evidence_row.get('recording_time_s', -1) - body_row['time_s']) > 1e-4):
            raise ValueError('original Native rail graph/frame/time join differs')
    hashes = json.loads((original / 'source-hashes.json').read_text())
    for name, digest in hashes.items():
        path = original / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('sealed original rail source differs: ' + name)
    for item in original.iterdir():
        if item.is_file():
            target = root / item.name
            if target.exists():
                raise ValueError('canonical rail source destination exists: ' + item.name)
            os.link(item, target)
    report = analyze(root, assignment_id=assignment_id, case_id=case_id,
                     expected_frames=expected_frames)
    (root / 'analysis-report.json').write_text(json.dumps(report, sort_keys=True) + '\n')
    (root / 'acquisition-provenance.json').write_text(json.dumps(
        {'provenance_kind': 'native', 'diagnostic_fixture': False}, sort_keys=True) + '\n')
    from worker_exchange.native_output import seal_capture
    seal = seal_capture(root, frames=expected_frames,
                        restoration={'restored': True, 'owner_release_readback': release},
                        errors=[], encoder_exit_codes={name: 0 for name in
                            ('overview', 'approach', 'reference_corner', 'driver_reference')},
                        context={'source_record': 'reviewed_original_railroad_crossing'})
    return {'frame_count': expected_frames, 'analysis': report,
            'capture_seal': seal, 'physical_acceptance_claimed': False}
