"""Independent saved-processing receipt check for the pedestrian crossing.

Synthetic diagnostics can establish software completion only. Original Native
attempts additionally need a source-bound crosswalk map readback and full 400
frame history before physical review can begin.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(version, attempt, case_id, construction_sha256):
    version = Path(version)
    attempt = Path(attempt)
    receipt = json.loads((version / 'processing.json').read_text())
    result_path = version / 'analysis' / 'result.json'
    result = json.loads(result_path.read_text())
    if (receipt.get('format') != 'worker-saved-processing' or
        receipt.get('case_id') != case_id or result.get('case_id') != case_id or
        receipt.get('recorded_only') is not True or receipt.get('passed') is not True):
        raise ValueError('saved processing case or lifecycle mismatch')
    if receipt.get('candidate_id') != 'primary':
        raise ValueError('unreviewed saved candidate selection')
    if (receipt.get('missing_evidence') is not False or
        receipt.get('originals_preserved') is not True or
        receipt.get('physical_acceptance_claimed') is not False or
        receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('saved evidence incomplete or unsupported acceptance claim')
    revision = receipt.get('analysis_revision', {})
    native = receipt.get('native_revision', {})
    if (revision.get('construction_sha256') != construction_sha256 or
        native.get('construction_sha256') != construction_sha256 or
        sha(attempt / 'construction.json') != construction_sha256 or
        receipt.get('result_sha256') != sha(result_path)):
        raise ValueError('saved construction/result hash mismatch')
    source_hashes = receipt.get('original_source_hashes', {})
    if not source_hashes or any(sha(attempt / name) != digest
                                for name, digest in source_hashes.items()):
        raise ValueError('saved original source changed')
    joins = receipt.get('timestamp_joins', {})
    decode = receipt.get('final_video_checks', {})
    if (joins.get('passed') is not True or joins.get('missing_original_trace_or_map') is not False or
        type(joins.get('frames')) is not int or joins['frames'] <= 0 or
        decode.get('passed') is not True or decode.get('frames') != joins['frames']):
        raise ValueError('saved frame join or full-video decode missing')
    diagnostic = result.get('provenance_kind') == 'synthetic_fixture' and result.get('diagnostic_fixture') is True
    if diagnostic:
        status = 'software_diagnostic_complete'
    elif result.get('provenance_kind') == 'native':
        if joins['frames'] != 400:
            raise ValueError('complete 400-frame Native crossing missing')
        if 'native-crosswalk-readback.json' not in source_hashes:
            raise ValueError('Native crosswalk map readback missing')
        packet = json.loads((attempt / 'native-crosswalk-readback.json').read_text())
        scene = json.loads((attempt / 'scene.json').read_text())
        if (packet.get('case_id') != case_id or
            packet.get('loaded_map_sha256') != scene.get('map_source_sha256') or
            packet.get('loaded_map_sha256') != sha(attempt / 'candidate-crossing.xodr')):
            raise ValueError('Native crosswalk source/case mismatch')
        polygons = packet.get('authored_polygon_readbacks')
        if (type(packet.get('native_crosswalk_vertices')) is not int or
            packet['native_crosswalk_vertices'] < 4 or
            not isinstance(polygons, list) or len(polygons) != len(scene.get('crosswalk_boundaries_xy_m', [])) or
            not all(type(item.get('vertices')) is int and item['vertices'] >= 4 and
                    type(item.get('maximum_vertex_readback_gap_m')) in (int, float) and
                    0 <= item['maximum_vertex_readback_gap_m'] <= 1 for item in polygons)):
            raise ValueError('Native crosswalk geometry readback incomplete')
        status = 'native_sources_ready_for_physical_review'
    else:
        raise ValueError('saved provenance unsupported')
    return {'case_id': case_id, 'status': status,
            'construction_sha256': construction_sha256,
            'processing_sha256': sha(version / 'processing.json'),
            'result_sha256': sha(result_path),
            'original_sources_checked': len(source_hashes),
            'frames': joins['frames'], 'physical_acceptance': False,
            'legal_verdict': 'unresolved'}
