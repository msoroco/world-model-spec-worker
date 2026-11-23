"""Audit selected C229597 source joins and current CPU receipts.

All input motion and camera material is a synthetic software fixture. This
script makes no claim about a Native run or the statutory judgment.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(data):
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def audit(case, remove_source=False):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((row for row in manifest['cases'] if row['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    suffix = case.rsplit('__', 1)[-1]
    if suffix not in ('reference', 'contrast'):
        raise ValueError('Unknown selected case suffix')
    spec = read(HERE / f'selected-{suffix}-fixture.json')
    files = dict(spec['files'])
    if remove_source:
        files.pop('trace.jsonl', None)
    for name in ('acquisition-provenance.json', 'trace.jsonl',
                 'video_frames.jsonl', 'capture/evidence.jsonl', 'road.xodr'):
        if name not in files:
            raise ValueError('Missing required source: ' + name)
    trace = lines(files['trace.jsonl'])
    mapping = lines(files['video_frames.jsonl'])
    evidence = lines(files['capture/evidence.jsonl'])
    if (len(trace) != 600 or len(mapping) != 600 or len(evidence) != 600):
        raise ValueError('Complete 600-frame source required')
    for i, (motion, frame, observation) in enumerate(zip(trace, mapping, evidence)):
        expected_frame = 1000 + i
        if (motion['frame'] != expected_frame or motion['video_frame'] != i
                or frame['carla_frame'] != expected_frame
                or frame['video_frame'] != i
                or observation['original_frame'] != expected_frame):
            raise ValueError('Original frame join differs')
        if any(abs(actual - i / 20) > 1e-6 for actual in
               (motion['time_s'], frame['time_s'], observation['recording_time_s'])):
            raise ValueError('Original time join differs')
        position = motion['position_m']
        if (len(position) != 3 or any(not math.isfinite(value) for value in position)
                or any(abs(a - b) > 1e-5 for a, b in
                       zip(position, observation['ego']['position_m']))):
            raise ValueError('Original pose/evidence join differs')
    compatibility = read(HERE / 'selected-proofs' / suffix / 'primary' / 'compatibility.json')
    saved = read(HERE / 'selected-saved-proofs' / suffix / 'processing.json')
    if (not compatibility['passed'] or compatibility['case_id'] != case
            or compatibility['construction_sha256'] != entry['construction_sha256']
            or not saved['passed'] or saved['case_id'] != case
            or saved['analysis_revision']['construction_sha256'] != entry['construction_sha256']
            or not saved['recorded_only'] or not saved['originals_preserved']
            or saved['missing_evidence'] or saved['final_video_checks']['frames'] != 600
            or not saved['final_video_checks']['passed']
            or saved['physical_acceptance_claimed']
            or saved['legal_acceptance_claimed']):
        raise ValueError('Current diagnostic receipt differs')
    for name in ('trace.jsonl', 'video_frames.jsonl', 'capture/evidence.jsonl',
                 'road.xodr', 'acquisition-provenance.json'):
        digest = hashlib.sha256(files[name].encode()).hexdigest()
        if (compatibility['fixture_manifest'].get(name) != digest
                or saved['original_source_hashes'].get(name) != digest):
            raise ValueError('Source hash differs: ' + name)
    if ({name + '.mkv' for name in VIEWS} - set(compatibility['fixture_manifest'])
            or {name + '.mkv' for name in VIEWS} - set(saved['original_source_hashes'])):
        raise ValueError('Four source camera bindings required')
    return {'case_id': case, 'passed': True, 'source_frames': 600,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'scope': 'synthetic CPU source and receipt checks; original pixels, participant behavior and physical completion require local capture',
            'accepted': False, 'native_executed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--remove-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.remove_source), indent=2))
