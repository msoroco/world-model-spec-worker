"""Independent CPU audit of retained C125714 delivery sources.

Diagnostic mode verifies synthetic fixtures without granting Native acceptance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from worker_exchange.media import audit as audit_video
from worker_exchange.measurement_contract import validate, verify_report

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
SOURCES = {'crossing_history.jsonl', 'road_geometry.json', 'video_frames.jsonl',
           'controller_history.jsonl'}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(case_id, attempt, package, diagnostic=False):
    attempt, package = Path(attempt), Path(package)
    manifest = _read(package / 'execution-manifest.json')
    matches = [entry for entry in manifest['cases'] if entry['case_id'] == case_id]
    if len(matches) != 1:
        raise ValueError('Unknown exact C125714 case')
    entry = matches[0]
    config, result = _read(attempt / 'config.json'), _read(attempt / 'result.json')
    if config.get('selected_case_id') != case_id or result.get('case_id') != case_id:
        raise ValueError('Exact case identity differs')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor'),
            config.get('rate_hz'), config.get('duration_s')) != (
            'NRS-484B-250-2', 'C125714', 'motor_vehicle_driver', 20, 55):
        raise ValueError('Exact law, cell, actor or capture profile differs')
    if result.get('physical_acceptance_claimed') is not False:
        raise ValueError('Source audit must not claim physical acceptance')
    provenance = result.get('provenance_kind')
    if diagnostic:
        if provenance != 'synthetic_fixture':
            raise ValueError('Diagnostic mode requires synthetic fixture provenance')
    elif provenance != 'native':
        raise ValueError('Delivery audit requires Native provenance')

    hashes = result.get('source_evidence_hashes')
    if not isinstance(hashes, dict) or not SOURCES <= set(hashes):
        raise ValueError('Missing original body, geometry, controller or frame-map source')
    for name, expected in hashes.items():
        if not (attempt / name).is_file() or _sha(attempt / name) != expected:
            raise ValueError('Missing or changed source: ' + name)
    if result.get('trace_reference') != 'trace.jsonl' or result.get('video_frame_map_reference') != 'video_frames.jsonl':
        raise ValueError('Original trace/frame-map reference differs')
    if result.get('capture_evidence_sha256') != _sha(attempt / 'capture/evidence.jsonl'):
        raise ValueError('Capture evidence changed')
    setup_sources = result.get('physical_checks', {}).get('setup', {}).get('sources', {})
    if setup_sources.get('trace.jsonl') != _sha(attempt / 'trace.jsonl'):
        raise ValueError('Original trace source hash differs')
    mapping = _rows(attempt / 'video_frames.jsonl')
    frames = len(mapping)
    if frames != (60 if diagnostic else 1100):
        raise ValueError('Original frame count differs from audit profile')
    previous_frame, previous_time = -1, -math.inf
    for index, row in enumerate(mapping):
        frame, time = row.get('carla_frame'), row.get('time_s')
        if (row.get('video_frame') != index or type(frame) is not int or frame <= previous_frame
                or type(time) not in (int, float) or not math.isfinite(time) or time <= previous_time):
            raise ValueError('Nonmonotone original frame/time join')
        if index and abs(time - previous_time - .05) > 1e-3:
            raise ValueError('Original sources are not 20 Hz')
        previous_frame, previous_time = frame, time
    if not diagnostic and abs(mapping[-1]['time_s'] - mapping[0]['time_s'] - 54.95) > .001:
        raise ValueError('Full planned capture duration missing')
    for name in ('trace.jsonl', 'crossing_history.jsonl', 'controller_history.jsonl'):
        rows = _rows(attempt / name)
        if len(rows) != frames or any(row.get('frame') != mapping[i]['carla_frame']
                                      or row.get('time_s') != mapping[i]['time_s'] for i, row in enumerate(rows)):
            raise ValueError('Original participant/controller join differs: ' + name)
    geometry = _read(attempt / 'road_geometry.json')
    if not geometry.get('intersection_polygon_xy_m') or not geometry.get('approach_geometry_source'):
        raise ValueError('Sourced crossing geometry missing')
    contract = _read(package / entry['measurement_contract'])
    plan = _read(package / 'case-plan.json')
    validate(contract, plan['requirement_dispositions'],
             (attempt / entry['measurement_procedure']['entrypoint']).read_text(), case_id)
    analysis = _read(attempt / 'analysis-report.json')
    if analysis.get('case_id') != case_id or analysis.get('physical_acceptance_claimed') is not False:
        raise ValueError('Analysis identity or physical-acceptance claim differs')
    measurements = verify_report(contract, analysis, attempt)
    if set(measurements) != {row['output_key'] for row in contract['requirements']} or len(measurements) < 3:
        raise ValueError('Missing source-bound subsection-2 measurements')
    videos = {name + '.mkv' for name in CAMERAS}
    if set(result.get('video_references', [])) != videos:
        raise ValueError('Four original camera references required')
    decodes = {}
    for name in CAMERAS:
        path = attempt / (name + '.mkv')
        receipt = audit_video(path, frames, mapping_sha256=_sha(attempt / 'video_frames.jsonl'))
        if receipt['dimensions'] != list(SIZES[name]):
            raise ValueError('Original camera dimensions differ: ' + name)
        decodes[name] = {'sha256': receipt['video_sha256'],
                         'frames': receipt['frames'], 'rgb_sequence_sha256': receipt['rgb_sequence_sha256']}
    return {'format': 'worker-c125714-independent-source-audit', 'case_id': case_id,
            'provenance_kind': provenance, 'diagnostic_only': diagnostic,
            'source_hashes': hashes, 'measurement_names': sorted(measurements),
            'camera_decodes': decodes, 'software_audit_passed': True,
            'actual_pixels_reviewed_for_physical_truth': False,
            'physical_acceptance_claimed': False, 'legal_conclusion': 'unresolved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    outcome = audit(args.case, args.attempt, args.package, diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': outcome['case_id'], 'software_audit_passed': True,
                      'diagnostic_only': outcome['diagnostic_only']}))
