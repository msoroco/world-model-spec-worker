"""Saved-only, source-sealed 20 Hz crosswalk measurements for C111610.

This checks frame and file integrity. It does not assert that a self-described
Native packet came from a physical CARLA run, nor decide legal right of way.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import crosswalk


class SavedSourceError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise SavedSourceError(message)


def read_sealed(attempt, index, name):
    entry = index.get('files', {}).get(name)
    require(isinstance(entry, dict), 'sealed source entry missing: ' + name)
    rel = entry.get('path')
    require(isinstance(rel, str) and rel and not Path(rel).is_absolute(), 'invalid source path: ' + name)
    root = Path(attempt).resolve()
    path = (root / rel).resolve()
    require(path.is_relative_to(root) and path.is_file(), 'source outside attempt or missing: ' + name)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    require(digest == entry.get('sha256'), 'source hash mismatch: ' + name)
    require(entry.get('source') == 'native_original', 'original source provenance missing: ' + name)
    return json.loads(path.read_text(encoding='utf-8')), {'path': rel, 'sha256': digest}


def _rows(value, label, expected):
    require(isinstance(value, list) and len(value) == expected, 'frame count mismatch: ' + label)
    for i, row in enumerate(value):
        require(isinstance(row, dict) and type(row.get('frame')) is int and row['frame'] == i,
                'non-contiguous original frame: ' + label)
        t = row.get('elapsed_s')
        require(isinstance(t, (int, float)) and math.isfinite(t) and abs(t-i/20) < 1e-5,
                '20 Hz original time mismatch: ' + label)
    return value


def process(attempt, scene_path, output):
    root = Path(attempt)
    index_path = root / 'source-index.json'
    require(index_path.is_file(), 'source-index.json missing')
    index = json.loads(index_path.read_text(encoding='utf-8'))
    require(index.get('format') == 'c111610-native-source-index-v1', 'wrong source index format')
    scene_path = Path(scene_path)
    scene = json.loads(scene_path.read_text(encoding='utf-8'))
    require(index.get('case_id') == scene['case_id'], 'exact case identity mismatch')
    require(index.get('scene_sha256') == hashlib.sha256(scene_path.read_bytes()).hexdigest(),
            'scene construction hash mismatch')
    require(scene['rate_hz'] == 20 and scene['duration_s'] == 30, 'unsupported capture duration/rate')
    frames = scene['rate_hz'] * scene['duration_s']
    site, site_source = read_sealed(root, index, 'site')
    ego, ego_source = read_sealed(root, index, 'ego')
    people, person_source = read_sealed(root, index, 'pedestrian')
    exception, exception_source = read_sealed(root, index, 'exception_review')
    site_bound = crosswalk.bind_site(site, index.get('map_name'), scene['turn_direction'])
    require(index.get('map_name') == site.get('map_name'), 'map identity mismatch')
    _rows(ego, 'ego', frames)
    _rows(people, 'pedestrian', frames)
    require(exception.get('source_refs') and exception.get('status') in
            ('none_identified', 'possible', 'applies'), 'exception review source missing')
    require(exception.get('case_id') == scene['case_id'], 'exception review case mismatch')
    if scene['official_device_condition'] != 'absent':
        require(site_bound['device_entries'], 'device state source missing')
    observations = []
    ego_ids, person_ids = set(), set()
    for i, (driver, person) in enumerate(zip(ego, people)):
        driver = dict(driver, source_ref=ego_source['path'] + '#' + str(i))
        person = dict(person, source_ref=person_source['path'] + '#' + str(i))
        measured = crosswalk.measure_frame(site_bound, i, driver, person, exception)
        ego_ids.add(driver['actor_id'])
        person_ids.add(person['actor_id'])
        observations.append(measured)
    require(len(ego_ids) == len(person_ids) == 1, 'participant identity drift')
    require(ego_ids.isdisjoint(person_ids), 'participant identity overlap')
    conditions = {row['device_condition'] for row in observations}
    require(len(conditions) == 1, 'official device state changed during capture')
    measured_condition = next(iter(conditions))
    occupied = sum(row['pedestrian_in_crosswalk'] and row['pedestrian_on_destination_half']
                   for row in observations)
    brake = sum(row['ego_brake'] for row in observations)
    result = {
        'format': 'c111610-saved-measurement-v1', 'case_id': scene['case_id'],
        'scene_sha256': index['scene_sha256'],
        'source_index_sha256': hashlib.sha256(index_path.read_bytes()).hexdigest(),
        'source_files': {'site': site_source, 'ego': ego_source,
                         'pedestrian': person_source, 'exception_review': exception_source},
        'frame_count': frames, 'rate_hz': 20, 'duration_s': 30,
        'measurements': observations,
        'summary': {'measured_device_condition': measured_condition,
                    'planned_device_condition_matches': measured_condition == scene['official_device_condition'],
                    'crosswalk_and_destination_half_frames': occupied,
                    'ego_brake_frames': brake,
                    'exception_review_status': exception['status']},
        'legal_judgment': 'unresolved', 'physical_source_verified': False,
        'camera_and_pixel_coverage_verified': False,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    process(args.attempt, args.scene, args.output)
