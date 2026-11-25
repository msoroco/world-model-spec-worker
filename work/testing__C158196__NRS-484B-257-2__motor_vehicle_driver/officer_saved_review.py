"""Validate independent original-frame review of an officer capture.

Programmed arm directions never become observed directions here. A reviewer
must identify the original camera frame for each observation and bind the
review to the exact capture and original camera bytes.
"""

import hashlib
import json
from pathlib import Path
import subprocess

from officer_direction import REFERENCE_SUFFIXES, behavior_suffix
from officer_capture_step import CAMERAS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _probe(path, frame_count):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name,nb_read_frames', '-of', 'json',
         str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get('streams', [])
    if (len(streams) != 1 or streams[0].get('codec_name') != 'ffv1' or
            streams[0].get('nb_read_frames') != str(frame_count)):
        raise ValueError('Original camera decode or frame count differs')


def validate(capture_path, review_path, camera_paths):
    capture_path, review_path = Path(capture_path), Path(review_path)
    capture = json.loads(capture_path.read_text())
    review = json.loads(review_path.read_text())
    if capture.get('format') != 'worker-subsection-2-officer-native-capture':
        raise ValueError('Original officer capture format missing')
    if behavior_suffix(capture.get('case_id')) in REFERENCE_SUFFIXES:
        raise ValueError('Reference-only case has no officer review')
    rows = capture.get('rows')
    if (not isinstance(rows, list) or len(rows) < 3 or
            len(rows) != capture.get('frame_count')):
        raise ValueError('Incomplete original officer capture')
    if (review.get('format') != 'worker-subsection-2-officer-original-frame-review' or
            review.get('case_id') != capture['case_id'] or
            review.get('capture_sha256') != _sha(capture_path) or
            not isinstance(review.get('reviewer'), str) or not review['reviewer']):
        raise ValueError('Independent original-frame review binding missing')
    if not isinstance(camera_paths, dict) or set(camera_paths) != set(CAMERAS):
        raise ValueError('Four original camera paths required')
    hashes = review.get('camera_sha256')
    if not isinstance(hashes, dict) or set(hashes) != set(CAMERAS):
        raise ValueError('Four original camera hashes required')
    for name in CAMERAS:
        if not Path(camera_paths[name]).is_file() or _sha(camera_paths[name]) != hashes[name]:
            raise ValueError('Original camera bytes differ: ' + name)
        _probe(camera_paths[name], len(rows))
    observations = review.get('frames')
    if not isinstance(observations, list) or len(observations) != len(rows):
        raise ValueError('Incomplete original-frame officer review')
    prior_frame = -1
    officer_id = None
    reviewed = []
    for index, (row, observation) in enumerate(zip(rows, observations)):
        frame = row.get('carla_frame')
        if type(frame) is not int or frame <= prior_frame or row.get('frame_index') != index:
            raise ValueError('Nonmonotone original officer frame')
        prior_frame = frame
        pose = row.get('officer_program')
        if not isinstance(pose, dict) or type(pose.get('officer_actor_id')) is not int:
            raise ValueError('Original officer actor identity missing')
        if officer_id is None:
            officer_id = pose['officer_actor_id']
        if pose['officer_actor_id'] != officer_id:
            raise ValueError('Officer actor identity changed')
        refs = row.get('camera_raw_sources')
        if not isinstance(refs, dict) or set(refs) != set(CAMERAS):
            raise ValueError('Four same-frame camera sources required')
        if any(not isinstance(refs[name], dict) or
               refs[name].get('carla_frame') != frame or
               refs[name].get('raw_source') not in (
                   name + '.mkv#frame-' + str(index),
                   str(camera_paths[name]) + '#frame-' + str(index))
               for name in CAMERAS):
            raise ValueError('Original officer camera frame source differs')
        source_ids = {refs[name]['raw_source'] for name in CAMERAS}
        if (not isinstance(observation, dict) or
                observation.get('carla_frame') != frame or
                observation.get('officer_actor_id') != officer_id or
                observation.get('direction_frame_source') not in source_ids or
                observation.get('authority_frame_source') not in source_ids or
                observation.get('control_frame_source') not in source_ids or
                observation.get('officer_direction_observed') not in
                {'stop', 'go', 'none', 'unclear'} or
                type(observation.get('police_authority_observed')) is not bool or
                type(observation.get('traffic_control_observed')) is not bool):
            raise ValueError('Original-frame officer observation differs from sources')
        reviewed.append({'carla_frame': frame,
                         'officer_actor_id': officer_id,
                         'officer_direction_observed':
                         observation['officer_direction_observed'],
                         'police_authority_observed':
                         observation['police_authority_observed'],
                         'traffic_control_observed':
                         observation['traffic_control_observed'],
                         'direction_frame_source':
                         observation['direction_frame_source'],
                         'authority_frame_source':
                         observation['authority_frame_source'],
                         'control_frame_source':
                         observation['control_frame_source']})
    return {'case_id': capture['case_id'], 'frame_count': len(rows),
            'capture_sha256': _sha(capture_path),
            'review_sha256': _sha(review_path),
            'camera_sha256': hashes, 'reviewed_frames': reviewed,
            'police_control_verified': all(row['police_authority_observed'] and
                                           row['traffic_control_observed']
                                           for row in reviewed)}
