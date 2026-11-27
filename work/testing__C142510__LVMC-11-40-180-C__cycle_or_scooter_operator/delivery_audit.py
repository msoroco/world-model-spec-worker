"""Independent original sidewalk delivery and controlled comparison audits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from sidewalk_overtake import ASSIGNMENT, measure

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FIXED_SITE = ('map_sha256', 'sidewalk_map_sha256', 'sidewalk_id',
              'sidewalk_polygon_xy_m', 'sidewalk_travel_unit_xy',
              'pedestrian_route_xyz_m', 'rider_route_xyz_m')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def decode_camera(path, expected_size):
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
         '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
         '-of', 'json', str(path)], capture_output=True, text=True,
        check=True, timeout=120)
    streams = json.loads(probe.stdout).get('streams', [])
    need(len(streams) == 1, 'one original camera stream required')
    item = streams[0]
    need(item.get('nb_read_frames') == '900' and
         item.get('r_frame_rate') in ('20/1', '20') and
         [item.get('width'), item.get('height')] == expected_size,
         'original camera frame profile differs')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True,
                   timeout=180)
    return {'frames': 900, 'fps': 20, 'size': expected_size}


def audit_attempt(attempt, case_id):
    """Require source-sealed original audio, histories and four decoded videos."""
    need(case_id.startswith(ASSIGNMENT + '__'), 'wrong exact sidewalk case')
    supplied = Path(attempt)
    need(supplied.is_dir() and not supplied.is_symlink(), 'original attempt missing')
    root = supplied.resolve()
    observation = measure(root)
    need(observation.get('case_id') == case_id and
         observation.get('legal_verdict_claimed') is False,
         'original measurement identity or disposition differs')
    site = read(root / 'site-context.json')
    need(site.get('case_id') == case_id and site.get('reviewer') and
         site.get('physical_surface_kind') == 'sidewalk' and
         site.get('sidewalk_connected') is True,
         'reviewed original connected sidewalk missing')
    need(all(site.get(key) is not None for key in FIXED_SITE),
         'fixed original sidewalk context incomplete')
    identity = read(root / 'capture-identity.json')
    need(identity.get('case_id') == case_id and
         identity.get('source_kind') == 'original_native_capture' and
         identity.get('diagnostic_fixture') is False and
         identity.get('source_manifest_sha256') == sha(root / 'source-manifest.json'),
         'original capture identity or source manifest binding missing')
    videos = identity.get('cameras')
    need(isinstance(videos, dict) and set(videos) == set(CAMERAS),
         'four original camera streams required')
    decodes = {}
    for name in CAMERAS:
        item = videos[name]
        rel = item.get('path') if isinstance(item, dict) else None
        need(isinstance(rel, str) and rel and not Path(rel).is_absolute()
             and '..' not in Path(rel).parts and item.get('frame_count') == 900,
             'original camera inventory invalid: ' + name)
        target = root / rel
        need(target.is_file() and not target.is_symlink() and
             target.resolve().parent == root and sha(target) == item.get('sha256'),
             'original camera bytes changed: ' + name)
        size = [1920, 1080] if name == 'overview' else [1280, 720]
        decodes[name] = decode_camera(target, size)
    return {'format': 'c142510-independent-original-audit-v1',
            'case_id': case_id, 'source_kind': 'original_native_capture',
            'source_manifest_sha256': sha(root / 'source-manifest.json'),
            'source_sha256': observation['source_sha256'],
            'fixed_site': {key: site.get(key) for key in FIXED_SITE},
            'rider_kind': site['rider_kind'], 'measurement': observation,
            'camera_decodes': decodes, 'legal_status': 'unresolved',
            'physical_acceptance': False}


def audit_comparisons(reports):
    """Check each declared pair, fixed original context and changed variable."""
    from sidewalk_overtake import compare

    plan = read(HERE / 'case-plan.json')
    need(set(reports) == {item['case_id'] for item in plan['cases']},
         'six exact original reports required')
    output = []
    for comparison in plan['comparisons']:
        left_id, right_id = comparison['case_ids']
        left, right = reports[left_id], reports[right_id]
        for report, cid in ((left, left_id), (right, right_id)):
            need(report.get('format') == 'c142510-independent-original-audit-v1' and
                 report.get('case_id') == cid and
                 report.get('source_kind') == 'original_native_capture' and
                 report.get('legal_status') == 'unresolved' and
                 report.get('physical_acceptance') is False and
                 report.get('source_sha256') == report.get('measurement', {}).get('source_sha256'),
                 'comparison includes nonoriginal or wrong-case audit')
        need(left.get('fixed_site') == right.get('fixed_site') and
             left.get('source_sha256', {}).get('road.xodr') ==
             right.get('source_sha256', {}).get('road.xodr') and
             (comparison['declared_difference'] == 'rider_kind' or
              left.get('rider_kind') == right.get('rider_kind')),
             'fixed original sidewalk or participant source changed')
        measured = compare(left['measurement'], right['measurement'],
                           comparison['declared_difference'])
        output.append({'comparison_id': comparison['comparison_id'],
                       'case_ids': [left_id, right_id],
                       'measured_difference': measured['declared_difference'],
                       'legal_status': 'unresolved',
                       'physical_acceptance': False})
    return output
