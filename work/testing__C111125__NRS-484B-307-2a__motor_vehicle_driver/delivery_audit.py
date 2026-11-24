"""Independent saved-media audit for the four straight circular-green cases.

This inspects original camera sources and frame identities. It does not decide
lawful presence, right of way, or physical visibility of the actors.
"""
from __future__ import annotations

import json
import subprocess

from native_scene import SourceError, require, source
from saved_attempt import process_saved

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
PRODUCTION_PROFILE = {
    'overview': (1920, 1080),
    'approach': (1280, 720),
    'reference_corner': (1280, 720),
    'driver_reference': (1280, 720),
}


def _probe(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-count_frames', '-show_entries',
         'stream=width,height,nb_read_frames,r_frame_rate',
         '-of', 'json', str(path)], capture_output=True, text=True)
    require(result.returncode == 0, 'ffprobe rejected original media')
    streams = json.loads(result.stdout).get('streams', [])
    require(len(streams) == 1, 'exactly one video stream required')
    return streams[0]


def _decode(path):
    result = subprocess.run(
        ['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0',
         '-f', 'null', '-'], capture_output=True, text=True)
    require(result.returncode == 0, 'original media full decode failed: ' + result.stderr[-300:])


def audit_saved_delivery(packet, root, *, profile=PRODUCTION_PROFILE,
                         diagnostic_fixture=False):
    """Return source-bound software checks for one sealed original attempt.

    A profile override requires the explicit diagnostic fixture flag; production
    delivery requires the declared 1080p/720p profile and 900 original frames.
    """
    require(profile == PRODUCTION_PROFILE or diagnostic_fixture,
            'profile override requires diagnostic fixture flag')
    summary = process_saved(packet, root)
    duration = summary['duration_frames']
    require(duration == 900 or diagnostic_fixture,
            'production capture requires 900 original frames')
    profile_ref = packet.get('camera_profile_ref')
    require(isinstance(profile_ref, dict), 'camera profile source required')
    declared_profile = json.loads(source(profile_ref, root).read_text(encoding='utf-8'))
    require(profile_ref['sha256'] == summary['camera_profile_sha256'],
            'camera profile hash binding differs')
    require(declared_profile.get('fps') == 20 and
            declared_profile.get('views') == {v: list(profile[v]) for v in VIEWS},
            'camera profile source differs from audited dimensions')
    context_ref = packet.get('context_ref')
    require(isinstance(context_ref, dict), 'reviewed context source required')
    context = json.loads(source(context_ref, root).read_text(encoding='utf-8'))
    require(context.get('official_head_id') == summary['official_head_id'],
            'reviewed context head identity differs')
    require(context.get('ego_approach_id') == summary['ego_approach_id'],
            'reviewed context approach identity differs')
    require(isinstance(context.get('other_devices_ref'), dict),
            'other-device source missing')
    source(context['other_devices_ref'], root)
    participant_refs = context.get('participant_context_refs')
    require(isinstance(participant_refs, dict), 'participant context inventory missing')
    participants = summary['exhibition']['other_users']
    require(set(participant_refs) == {u['id'] for u in participants},
            'participant context identity differs')
    for participant in participants:
        ref = participant_refs[participant['id']]
        require(isinstance(ref, dict) and
                ref['path'] == participant['lawful_presence_source'],
                'lawful-presence source binding differs')
        source(ref, root)
    frame_ref = packet.get('frame_map_ref')
    require(isinstance(frame_ref, dict), 'original frame-map source required')
    frame_map = json.loads(source(frame_ref, root).read_text(encoding='utf-8'))
    require(isinstance(frame_map, list) and len(frame_map) == duration,
            'original frame-map length mismatch')
    event_frames = [row['frame'] for row in summary['records']]
    for i, row in enumerate(frame_map):
        require(row.get('frame') == event_frames[i] and row.get('index') == i,
                'original frame-map event join or index mismatch')
        require(row.get('camera_frame_ids') and
                set(row['camera_frame_ids']) == set(VIEWS),
                'four original camera frame identities required')
        require(all(isinstance(row['camera_frame_ids'][v], int)
                    for v in VIEWS), 'invalid camera frame identity')
        require(all(row['camera_frame_ids'][v] == row['frame'] for v in VIEWS),
                'camera frame not synchronized to original event')
    require(set(profile) == set(VIEWS), 'four-camera profile required')
    media = packet.get('camera_media_refs')
    require(isinstance(media, dict) and set(media) == set(VIEWS),
            'four original camera media references required')
    checked = {}
    for view in VIEWS:
        ref = media[view]
        require(isinstance(ref, dict), 'camera source hash required: ' + view)
        path = source(ref, root)
        stream = _probe(path)
        require((stream.get('width'), stream.get('height')) == tuple(profile[view]),
                'camera dimensions differ: ' + view)
        require(stream.get('r_frame_rate') == '20/1', 'camera fps differs: ' + view)
        require(int(stream.get('nb_read_frames', -1)) == duration,
                'camera original frame count differs: ' + view)
        _decode(path)
        checked[view] = {'source': ref, 'frames': duration,
                         'width': stream['width'], 'height': stream['height'],
                         'full_decode': True}
    return {'case_id': summary['case_id'], 'attempt_id': summary['attempt_id'],
            'recording_id': summary['recording_id'], 'original_event_ref': packet['event_ref'],
            'original_frame_map_ref': frame_ref, 'context_ref': context_ref,
            'camera_profile_ref': profile_ref,
            'camera_media': checked,
            'frame_count': duration, 'fps': 20, 'software_audit_passed': True,
            'diagnostic_fixture': diagnostic_fixture,
            'physical_acceptance_claimed': False, 'lawful_presence_verdict': None,
            'right_of_way_verdict': None}
