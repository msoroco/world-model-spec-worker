"""Export sealed original C125751 sources to the pinned saved-processing shape.

This builds derived copies in a distinct directory. It does not
assert that the authored controls realized a statutory right-of-way outcome.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

from saved_delivery import audit as audit_original

ROLES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('front', 'rear', 'left', 'right')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export(attempt, survey_path, destination, profile=None):
    """Copy source joins and encode four lossless videos from sealed PNGs."""
    from scenario_pipeline.worker_exchange.capture import PROFILE
    from scenario_pipeline.worker_exchange.media import audit as audit_video

    attempt = Path(attempt).resolve()
    destination = Path(destination).resolve()
    if destination == attempt or destination in attempt.parents:
        raise ValueError('derived source export must not replace original acquisition')
    if destination.exists():
        raise ValueError('retain prior source export; use a fresh destination')
    packet = audit_original(attempt, survey_path, decode_media=True)
    survey = json.loads(Path(survey_path).read_text())
    mapping = survey.get('runtime_camera_roles')
    if not isinstance(mapping, dict) or set(mapping) != set(ROLES) or set(mapping.values()) != set(CHANNELS):
        raise ValueError('reviewed one-to-one runtime camera role mapping required')
    profile = PROFILE if profile is None else profile
    sizes = dict(zip(ROLES, [profile['overview'], *profile['detail_views']]))
    if profile['fps'] != 20 or len(profile['detail_views']) != 3:
        raise ValueError('runtime four-camera 20 Hz profile required')
    trace = json.loads((attempt/'original-trace.json').read_text())
    index = json.loads((attempt/'original-camera-index.json').read_text())['channels']
    if len(trace['frames']) != 900:
        raise ValueError('full original 900-frame trace required')
    destination.mkdir(parents=True)
    shutil.copy2(attempt/'video_frames.jsonl', destination/'video_frames.jsonl')
    with (destination/'trace.jsonl').open('w') as target:
        previous = None
        for row in trace['frames']:
            vertices = row['ego']['body_vertices_xy_m']
            center = [sum(point[axis] for point in vertices)/len(vertices) for axis in (0, 1)]
            if previous is None:
                speed = heading = 0.0
            else:
                dt = row['native_elapsed_seconds']-previous[2]
                if dt <= 0:
                    raise ValueError('original Native clock must increase')
                dx,dy = center[0]-previous[0],center[1]-previous[1]
                speed = math.hypot(dx,dy)/dt
                heading = math.degrees(math.atan2(dy,dx)) if speed else 0.0
            sample = {'frame': row['native_frame_id'], 'time_s': row['native_elapsed_seconds'],
                      'position': {'x':center[0], 'y':center[1], 'z':0.0},
                      'heading_deg':heading, 'speed_mps':speed,
                      'body_vertices_m': vertices,
                      'road_id': row['ego']['road_id'],
                      'other_body_vertices_m': row['other']['body_vertices_xy_m'],
                      'governing_device_readback': row['governing_device_readback']}
            target.write(json.dumps(sample, separators=(',', ':'))+'\n')
            previous = (center[0],center[1],row['native_elapsed_seconds'])
    videos = {}
    for role in ROLES:
        channel = mapping[role]
        rows = index[channel]
        first = rows[0]['frame']
        if any(row['frame'] != first+offset for offset, row in enumerate(rows)):
            raise ValueError('original camera frame IDs are not consecutive: '+channel)
        first_source = attempt/'media'/channel/(str(first)+'.png')
        from PIL import Image
        with Image.open(first_source) as image:
            if list(image.size) != sizes[role]:
                raise ValueError('original camera does not match runtime role dimensions: '+role)
        video = destination/(role+'.mkv')
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                   '-framerate', '20', '-start_number', str(first), '-i',
                   str(attempt/'media'/channel/'%d.png'), '-frames:v', '900',
                   '-an', '-c:v', 'ffv1', '-pix_fmt', 'yuv444p', str(video)]
        subprocess.run(command, check=True, timeout=3600)
        decoded = audit_video(video, 900, mapping_sha256=packet['frame_map_sha256'])
        if decoded['frames'] != 900 or not decoded['passed']:
            raise ValueError('full original camera export decode required: '+role)
        videos[role] = {'source_channel': channel, 'sha256': digest(video),
                        'decoded_frames': decoded['frames'], 'source_frame_count': len(rows)}
    if audit_original(attempt, survey_path, decode_media=False)['source_integrity'] != 'passed':
        raise ValueError('original acquisition changed during source export')
    receipt = {'format': 'c125751-runtime-source-export', 'case_id': packet['case_id'],
               'original_source_manifest_sha256': digest(attempt/'source-manifest.json'),
               'frame_map_sha256': packet['frame_map_sha256'],
               'trace_sha256': digest(destination/'trace.jsonl'),
               'videos': videos, 'original_sources_preserved': True,
               'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    (destination/'source-export.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt
