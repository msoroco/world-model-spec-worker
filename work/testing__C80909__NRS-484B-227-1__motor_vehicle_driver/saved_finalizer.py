"""Saved C80909 divider observations from original Native and camera sources."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from divider_measurements import analyze
from native_capture import CAMERAS
from shapely.geometry import Polygon


def _video_info(path):
    probe = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height,r_frame_rate,nb_read_frames',
        '-of', 'json', str(path)], capture_output=True, text=True)
    if probe.returncode:
        raise ValueError('Original camera frame probe failed: ' + path.name)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('One original camera video stream required: ' + path.name)
    decode = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                             '-an', '-f', 'null', '-'], capture_output=True, text=True)
    if decode.returncode or decode.stderr.strip():
        raise ValueError('Full original camera decode failed: ' + path.name)
    return streams[0]


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def finalize(root, *, probe=_video_info):
    root = Path(root)
    observations = analyze(root)
    context = json.loads((root / 'divider_context.json').read_text())
    site_path = root / 'site_source_receipt.json'
    barrier_path = root / 'barrier_receipt.json'
    if not site_path.is_file() or not barrier_path.is_file():
        raise ValueError('Missing original site or barrier source receipt')
    site = json.loads(site_path.read_text())
    barrier = json.loads(barrier_path.read_text())
    if site.get('native_map_name') != context['native_map_id'] or not site.get('source_refs'):
        raise ValueError('Original site source binding differs')
    for ref in site['source_refs']:
        source = (root / ref['path']).resolve()
        if not source.is_relative_to(root.resolve()) or not source.is_file() or _sha256(source) != ref['sha256']:
            raise ValueError('Original site source missing or changed')
    opening = Polygon(context['opening_xy_m'])
    if not Polygon(barrier.get('opening_xy_m', [])).equals(opening):
        raise ValueError('Original barrier opening differs')
    sections = barrier.get('barrier_footprints_xy_m', [])
    offsets = barrier.get('section_axis_offsets_m', [])
    if (len(sections) != 2 or len(offsets) != 2 or offsets[0] * offsets[1] >= 0 or
            any(Polygon(section).intersects(opening) for section in sections)):
        raise ValueError('Original barrier sections do not straddle clear opening')
    case_id = site.get('case_id')
    allowed = {'testing__C80909__NRS-484B-227-1__motor_vehicle_driver__' + name
               for name in ('left_through_opening', 'left_across_blocked_divider',
                            'left_right_roadway_continuation',
                            'left_at_established_crossover')}
    if case_id not in allowed:
        raise ValueError('Exact C80909 source case identity required')
    if case_id.endswith('__left_at_established_crossover'):
        authority = site.get('authority_source_ref')
        if not isinstance(authority, dict) or authority not in site['source_refs']:
            raise ValueError('Missing separate public-authority source binding')
    observations['site_context_sources'] = {
        'native_map_name': site['native_map_name'],
        'case_id': case_id,
        'source_refs': site['source_refs'],
        'site_source_sha256': _sha256(site_path),
        'barrier_source_sha256': _sha256(barrier_path)}
    count = len(observations['samples'])
    if count < 4:
        raise ValueError('Incomplete Native movement history')
    sources = {}
    for name, (width, height) in CAMERAS.items():
        path = root / (name + '.mkv')
        if not path.is_file():
            raise ValueError('Missing original source camera: ' + name)
        info = probe(path)
        if (info.get('codec_name') != 'ffv1' or
                (info.get('width'), info.get('height')) != (width, height) or
                info.get('r_frame_rate') != '20/1' or
                str(info.get('nb_read_frames')) != str(count)):
            raise ValueError('Original camera profile or frame count differs: ' + name)
        sources[name] = {'path': path.name,
                         'sha256': _sha256(path),
                         'decoded_frames': count, 'width': width, 'height': height}
    observations['camera_sources'] = sources
    observations['measurement_contract'] = {
        'case_id': case_id,
        'complete_body_crossing': 'source geometry, not legal verdict',
        'heading_change': 'signed original Native yaw difference',
        'public_authority_establishment': 'requires independent original source review',
        'physical_completion': 'requires independent original camera review'}
    observations['physical_acceptance_claimed'] = False
    return observations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize_delivery(args.attempt, args.output)


def finalize_delivery(attempt, output, *, probe=_video_info):
    """Write the canonical saved result and a separate observational report."""
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Fresh saved analysis and result paths required')
    required = ('config.json', 'construction.json', 'trace.jsonl',
                'capture/evidence.jsonl', 'video_frames.jsonl',
                'movement_history.jsonl', 'divider_context.json',
                'barrier_receipt.json', 'site_source_receipt.json')
    for name in required:
        source = attempt / name
        if not source.is_file() or not source.stat().st_size:
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    if (config.get('selected_case_id') != construction.get('case_id') or
            config.get('law_id') != 'NRS-484B-227-1' or config.get('cell_id') != 'C80909'):
        raise ValueError('Saved exact C80909 identity differs')
    observations = finalize(attempt, probe=probe)
    rows = [[json.loads(line) for line in (attempt / name).read_text().splitlines() if line]
            for name in ('movement_history.jsonl', 'video_frames.jsonl',
                         'trace.jsonl', 'capture/evidence.jsonl')]
    if len({len(group) for group in rows}) != 1:
        raise ValueError('Original Native source history lengths differ')
    for movement, frame, trace, evidence in zip(*rows):
        native_frame, time_s = frame['carla_frame'], frame['time_s']
        if (movement['frame'] != native_frame or trace['frame'] != native_frame or
                evidence['original_frame'] != native_frame or
                abs(movement['time_s'] - time_s) > 1e-4 or
                abs(trace['time_s'] - time_s) > 1e-4):
            raise ValueError('Original Native source frame/time join differs')
    source_hashes = {name: _sha256(attempt / name) for name in required}
    source_hashes.update({name + '.mkv': info['sha256']
                          for name, info in observations['camera_sources'].items()})
    measured = {key: observations[key] for key in (
        'starts_on_right_hand_roadway', 'ends_on_destination_roadway',
        'opening_traversed_observed', 'any_body_overlap_outside_opening',
        'observed_turn_angle_degrees')}
    measured['sample_count'] = len(observations['samples'])
    check = {'target': 'left_turn_or_right_roadway_route',
             'requested': config['physical_completion']['criterion'],
             'measured': measured,
             'method': 'source-bound complete-body divider and heading analysis',
             'tolerance': 'engineering only; statutory judgment unresolved',
             'matched': False, 'physical_cause_confirmed': False,
             'cause_evidence': ['movement_history.jsonl', 'divider_context.json',
                                'barrier_receipt.json', 'video_frames.jsonl']}
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [check], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Saved source assessment; physical and legal review pending',
              'physical_failure_flags': ['Actual Native site and authority status require independent review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': [{'name': key, 'reference': key, 'sha256': value}
                                     for key, value in source_hashes.items()],
              'source_evidence_hashes': source_hashes, 'realized_observables': {}}
    from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    write_result(attempt, result)
    report = {'format': 'worker-divided-highway-left-turn-analysis',
              'case_id': config['selected_case_id'], 'source_sha256': source_hashes,
              'measurements': measured, 'source_observations': observations,
              'physical_checks': result['physical_checks'],
              'legal_conclusion': 'unresolved', 'analysis_complete': True}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    main()
