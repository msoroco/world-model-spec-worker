"""Saved-only checks for the exact bicycle encounter attempts.

Camera metadata establishes a complete, source-bound stream, not visibility of
the rider in decoded pixels. The latter remains an independent physical review.
"""
from __future__ import annotations

import json
import math
import subprocess
from fractions import Fraction
from bicycle_encounter import MODES, read_source, require, verify_site


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FPS = 20
DURATION_FRAMES = 900


def probe_video(path):
    """Count decoded video frames with the pinned ffprobe executable."""
    command = ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
               '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames',
               '-of', 'json', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get('streams', [])
    require(len(streams) == 1, 'exactly one selected video stream required')
    stream = streams[0]
    rate = Fraction(stream['avg_frame_rate'])
    require(rate.denominator != 0, 'invalid video frame rate')
    return {'fps': float(rate), 'frame_count': int(stream['nb_read_frames']),
            'width': int(stream['width']), 'height': int(stream['height'])}


def finalize(site, root, event_ref, camera_sources, mode, probe, frames=DURATION_FRAMES):
    """Validate saved original sources and summarize observed motion/commands.

    ``probe(path)`` must return decoded stream metadata with fps, frame_count,
    width and height. Production callers should use ffprobe plus a full decoder;
    tests inject it so they never claim a physical recording exists.
    """
    require(mode in MODES, 'unknown encounter mode')
    require(isinstance(frames, int) and frames >= 3, 'invalid duration')
    crossings = verify_site(site, root)
    require(set(camera_sources) == set(VIEWS), 'four exact camera sources required')
    source_paths = {}
    camera_metadata = {}
    for view in VIEWS:
        ref = camera_sources[view]
        source_paths[view] = read_source(ref, root)
        meta = probe(source_paths[view])
        require(isinstance(meta, dict), 'camera probe metadata missing')
        require(meta.get('fps') == FPS and meta.get('frame_count') == frames,
                'camera frame rate or duration mismatch: ' + view)
        require(all(isinstance(meta.get(k), int) and meta[k] > 0
                    for k in ('width', 'height')), 'camera dimensions missing: ' + view)
        camera_metadata[view] = {k: meta[k] for k in ('fps', 'frame_count', 'width', 'height')}
    require(len(set(source_paths.values())) == len(VIEWS), 'camera sources must be distinct')

    rows = json.loads(read_source(event_ref, root).read_text(encoding='utf-8'))
    require(isinstance(rows, list) and len(rows) == frames, 'Original history duration mismatch')
    first = rows[0].get('frame')
    require(isinstance(first, int) and first >= 0, 'first Original frame missing')
    gaps = []
    mode_frames = 0
    waiting_frames = 0
    travel_frames = 0
    observed_rider_motion_m = 0.0
    observed_ego_motion_m = 0.0
    previous = None
    for index, row in enumerate(rows):
        require(row.get('frame') == first + index, 'noncontinuous Original frames')
        require(row.get('ego_id') == site['ego_actor_id'] and
                row.get('rider_id') == site['rider_actor_id'], 'actor identity changed')
        require(row.get('ego_blueprint_id') == site['ego_blueprint_id'] and
                row.get('rider_blueprint_id') == site['bicycle_blueprint_id'],
                'actor type changed')
        require(row.get('mode_command') == mode and
                row.get('command_source') in ('controller_log', 'human_input_log'),
                'Original command source/mode missing')
        require(row.get('rider_visual_present') in (True, False),
                'rider visual annotation missing')
        require(row.get('legal_verdict') is None, 'unsupported legal verdict supplied')
        require(row.get('camera_frame') == row['frame'], 'camera/telemetry frame join mismatch')
        for key in ('ego_xy', 'rider_xy'):
            require(isinstance(row.get(key), list) and len(row[key]) == 2 and
                    all(isinstance(v, (int, float)) and math.isfinite(v) for v in row[key]),
                    'nonfinite Original pose: ' + key)
        speed = row.get('target_speed_mps')
        require(isinstance(speed, (int, float)) and math.isfinite(speed) and speed >= 0,
                'commanded target speed missing')
        waiting_frames += speed == 0
        travel_frames += speed > 0
        mode_frames += 1
        gaps.append(math.dist(row['ego_xy'], row['rider_xy']))
        if previous is not None:
            observed_ego_motion_m += math.dist(previous['ego_xy'], row['ego_xy'])
            observed_rider_motion_m += math.dist(previous['rider_xy'], row['rider_xy'])
        previous = row
    require(observed_rider_motion_m > 0, 'rider movement absent in Original poses')
    if mode == 'maintain_clearance':
        require(waiting_frames > 0, 'waiting command absent')
    else:
        require(travel_frames > 0, 'travel command absent')
    return {
        'assignment_id': site['assignment_id'], 'mode': mode,
        'first_frame': first, 'frame_count': mode_frames, 'fps': FPS,
        'crossings_xy': [list(p) for p in crossings],
        'minimum_center_gap_m': min(gaps),
        'observed_ego_motion_m': observed_ego_motion_m,
        'observed_rider_motion_m': observed_rider_motion_m,
        'waiting_command_frames': waiting_frames,
        'travel_command_frames': travel_frames,
        'camera_metadata': camera_metadata,
        'original_sources': site['original_sources'] + [event_ref] +
                            [camera_sources[v] for v in VIEWS],
        'rider_visual_annotation_frames': sum(r['rider_visual_present'] for r in rows),
        'pixel_visibility_verified': False,
        'lawful_riding_verdict': None, 'intent_verdict': None,
        'interference_verdict': None,
    }
