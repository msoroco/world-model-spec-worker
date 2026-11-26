"""Independent original-source, walking-side and camera-pixel delivery audit.

Diagnostic mode exercises software on the synthetic source-shaped fixture. The
ordinary mode requires separately reviewed original Native map and pixels.
"""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_pixels(path, width, height, expected, diagnostic):
    frame_size = width * height * 3
    black = hashlib.sha256(bytes(frame_size)).hexdigest()
    decoder = subprocess.Popen(
        ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-f', 'rawvideo',
         '-pix_fmt', 'rgb24', '-vsync', '0', '-'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for item in expected:
            frame = decoder.stdout.read(frame_size)
            require(len(frame) == frame_size, 'Camera source ended before frame map')
            actual = hashlib.sha256(frame).hexdigest()
            if diagnostic:
                require(actual == black, 'Diagnostic camera pixels differ from fixture recipe')
            else:
                require(actual == item, 'Original camera pixel hash differs')
        require(decoder.stdout.read(1) == b'', 'Camera source has extra frames')
        error = decoder.stderr.read().decode('utf-8', errors='replace')
        require(decoder.wait(timeout=120) == 0, 'Camera decode failed: ' + error[-400:])
    finally:
        if decoder.poll() is None:
            decoder.kill()
            decoder.wait()


def audit(case, candidate, attempt, processing_path, diagnostic):
    attempt = Path(attempt).resolve()
    processing = read(processing_path)
    config = read(attempt / 'config.json')
    require(config['case_id'] == config['selected_case_id'] == case and
            config['law_id'] == 'NRS-484B-297-2' and config['cell_id'] == 'C230259' and
            config['actor'] == 'pedestrian', 'Exact pedestrian law/cell/case differs')
    require(config['duration_s'] == 30 and config['rate_hz'] == 20 and config['frames'] == 600,
            'Complete 30-second walking interval differs')
    require(processing['case_id'] == case and processing['candidate_id'] == candidate and
            processing['passed'] is True and processing['recorded_only'] is True and
            processing['originals_preserved'] is True, 'Saved-only processing proof differs')
    selection_path = attempt / 'candidate-selection.json'
    if selection_path.is_file():
        selection = read(selection_path)
        require(selection['candidate_id'] == candidate and selection['case_id'] == case,
                'Selected candidate differs')
    else:
        require(candidate == 'primary' and diagnostic, 'Fallback candidate selection missing')
    require(sha(attempt / 'construction.json') == processing['native_revision']['construction_sha256'],
            'Original construction changed')
    for name, digest in processing['original_source_hashes'].items():
        require((attempt / name).is_file() and sha(attempt / name) == digest,
                'Original acquisition changed: ' + name)
    walking = rows(attempt / 'walking-source.jsonl')
    frame_map = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    native = rows(attempt / 'capture/native/frames.jsonl')
    require(all(len(item) == 600 for item in (walking, frame_map, trace, evidence, native)),
            'Full original source interval missing')
    context = read(attempt / 'reviewed-road-source.json')
    require(all(context.get(key) for key in
                ('highway_authority_source', 'highway_boundary_source',
                 'sidewalk_inventory_source', 'subsection_6_obstruction_source',
                 'traffic_route_source')), 'Highway authority or sidewalk source missing')
    require(context.get('sidewalk_present') is False and
            context.get('subsection_6_obstruction') is False,
            'No-sidewalk branch or subsection 6 context differs')
    traffic = context['traffic_direction_xy']
    anchor = context['highway_centerline_anchor_xy_m']
    half_width = context['highway_half_width_m']
    require(len(traffic) == len(anchor) == 2 and math.hypot(*traffic) > 0 and
            isinstance(half_width, (int, float)) and half_width > 0,
            'Reviewed highway direction or boundary invalid')
    norm = math.hypot(*traffic)
    traffic = [traffic[0] / norm, traffic[1] / norm]
    wanted_side = 1 if config['condition'] == 'a' else -1
    subject_id = walking[0]['pedestrian_id']
    vehicle_id = walking[0]['vehicle_id']
    vehicle_progress_m = 0.0
    for index, (walk, mapping, movement, source, graph) in enumerate(
            zip(walking, frame_map, trace, evidence, native)):
        frame = mapping['native_frame']
        require(mapping['video_frame'] == index and frame == mapping['carla_frame'] ==
                walk['native_frame'] == movement['frame'] == source['original_frame'] ==
                graph['frame'], 'Original frame identity join differs')
        require(walk['pedestrian_id'] == subject_id == source['actor_id'] and
                walk['vehicle_id'] == vehicle_id and subject_id != vehicle_id,
                'Original participant identity differs')
        require(abs(mapping['time_s'] - walk['time_s']) < 1e-4 and
                abs(mapping['time_s'] - movement['time_s']) < 1e-4 and
                abs(mapping['time_s'] - source['recording_time_s']) < 1e-4,
                'Original timestamp join differs')
        pedestrian = walk['pedestrian_xy_m']
        require(all(abs(a - b) < .002 for a, b in
                    zip(pedestrian, source['ego']['position_m'][:2])),
                'Original pedestrian pose differs')
        offset = [pedestrian[0] - anchor[0], pedestrian[1] - anchor[1]]
        signed = traffic[0] * offset[1] - traffic[1] * offset[0]
        require(wanted_side * signed > 0 and abs(signed) < half_width,
                'Continuous authored highway side differs')
        heading = walk['pedestrian_heading_xy']
        require(heading[0] * traffic[0] + heading[1] * traffic[1] < 0,
                'Pedestrian does not face approaching traffic')
        if index:
            last = walking[index - 1]['vehicle_xy_m']
            vehicle = walk['vehicle_xy_m']
            step_m = ((vehicle[0] - last[0]) * traffic[0] +
                      (vehicle[1] - last[1]) * traffic[1])
            require(step_m >= -.01, 'Other vehicle reverses along the sourced route')
            vehicle_progress_m += step_m
    require(vehicle_progress_m > 1.0,
            'Other vehicle lacks measured approach along the sourced route')
    result = read(attempt / 'result.json')
    require(result['case_id'] == case and result.get('legal_verdict') is None,
            'Analyzer assigned a legal verdict')
    if diagnostic:
        require(context['source_kind'] == 'synthetic_diagnostic' and
                read(attempt / 'acquisition-provenance.json')['diagnostic_fixture'] is True,
                'Diagnostic mode requires a synthetic source')
    else:
        require(context['source_kind'] == 'original_native', 'Original Native source required')
        review = read(attempt / 'independent-source-review.json')
        require(review.get('reviewer') and review.get('native_map_reviewed') is True and
                review.get('sidewalk_inventory_reviewed') is True and
                review.get('pedestrian_pixels_reviewed') is True and
                review.get('vehicle_pixels_reviewed') is True and
                review.get('frame_count') == 600,
                'Independent original highway, body and pixel review required')
        require(review.get('source_hashes') and
                all(sha(attempt / name) == digest for name, digest in
                    review['source_hashes'].items()),
                'Independent original source hashes differ')
        require(result['physical_checks']['maneuver']['status'] == 'met',
                'Physical pedestrian route completion not established')
    for name, (width, height) in CAMERAS.items():
        hashes = ([mapping.get('source_rgb_sha256', {}).get(name) for mapping in frame_map]
                  if not diagnostic else [None] * len(frame_map))
        if not diagnostic:
            require(all(hashes), 'Original camera pixel hashes missing')
        inspect_pixels(attempt / (name + '.mkv'), width, height, hashes, diagnostic)
    return {'format': 'worker-pedestrian-highway-delivery-audit-v1',
            'case_id': case, 'candidate_id': candidate, 'diagnostic': diagnostic,
            'passed': True, 'source_frames': 600, 'cameras': list(CAMERAS),
            'original_native_accepted': not diagnostic, 'legal_verdict_claimed': False,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion']}


def main():
    parser = argparse.ArgumentParser()
    for name in ('case', 'candidate', 'attempt', 'processing', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing, args.diagnostic)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
