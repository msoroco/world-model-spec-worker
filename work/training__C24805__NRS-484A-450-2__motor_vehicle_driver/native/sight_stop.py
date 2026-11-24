"""Source-bound stop and hierarchy diagnostic; no legal visibility cutoff."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

FRAMES = 600
HZ = 20
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check_config(config, road_text):
    prefix = 'training__C24805__NRS-484A-450-2__motor_vehicle_driver__'
    if (config.get('case_id') not in (prefix + 'probe_a', prefix + 'probe_b')
            or config.get('law_id') != 'NRS-484A-450-2'
            or config.get('cell_id') != 'C24805'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('duration_s') != 30 or config.get('rate_hz') != HZ
            or config.get('frames') != FRAMES or config.get('legal_verdict') is not None
            or config.get('physical_completion') is not False):
        raise ValueError('C24805 exact identity or duration differs')
    if tuple(c.get('name') for c in config.get('cameras', ())) != CAMERAS:
        raise ValueError('Four named source cameras required')
    if any(c.get('fps') != HZ or not all(c.get(k) for k in
           ('width', 'height', 'fov_deg', 'location_xyz_m', 'rotation_pyr_deg'))
           for c in config['cameras']):
        raise ValueError('Camera dimensions or pose missing')
    road = next((r for r in ET.fromstring(road_text).findall('road')
                 if r.get('id') == '1'), None)
    if road is None or not any(s.get('name') == 'STOP' and s.get('orientation') == '-'
                             for s in road.findall('signals/signal')):
        raise ValueError('Governing approach stop sign missing')
    if any(o.get('type') in ('crosswalk', 'stopLine') or 'stop' in
           o.get('name', '').lower() for o in road.findall('objects/object')):
        raise ValueError('Crosswalk or stop-line reference present')
    if road.find('./planView/geometry') is None:
        raise ValueError('Approach road geometry missing')
    if not config.get('unmarked_crosswalk_source_audit_required') or not config.get('sight_source_required'):
        raise ValueError('Native unmarked-crosswalk and sight source audits required')
    return {'case_id': config['case_id'], 'frames': FRAMES,
            'source_cameras': list(CAMERAS), 'authored_marked_references_absent': True,
            'unmarked_crosswalk_absence_verified': False,
            'driver_sight_observed': False, 'physical_completion': False,
            'carla_contacted': False}


def measure(rows, source_kind):
    if source_kind not in ('authored_native_request', 'original_native'):
        raise ValueError('Unrecognized source kind')
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame source required')
    stop_frames = []
    entry = None
    previous = None
    for i, row in enumerate(rows):
        if row.get('frame') != i or abs(row.get('time_s', -1) - (i + 1) / HZ) > 1e-8:
            raise ValueError('Frame/time join differs')
        if row.get('source_kind') != source_kind:
            raise ValueError('Frame source differs')
        center = row.get('ego_center_xy_m')
        speed = row.get('ego_speed_mps')
        if (not isinstance(center, list) or len(center) != 2
                or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in center)
                or not isinstance(speed, (int, float)) or not math.isfinite(speed)
                or speed < 0):
            raise ValueError('Original position or speed missing')
        if previous is not None and center[1] + 1e-6 < previous:
            raise ValueError('Approach trajectory reverses')
        previous = center[1]
        # Front-body offset is a diagnostic geometry assumption until original
        # Native vertices are retained. It is never a legal stopping boundary.
        front_y = center[1] + 2.0
        if entry is None and front_y >= -7:
            entry = i
        if entry is None and speed <= 0.15:
            stop_frames.append(i)
    if entry is None:
        raise ValueError('Intersection entry absent')
    best = run = 0
    stopped = set(stop_frames)
    for i in range(entry):
        run = run + 1 if i in stopped else 0
        best = max(best, run)
    return {'format': 'c24805-stop-request-meter-v1',
            'source_kind': source_kind, 'frames': FRAMES,
            'entry_frame': entry, 'longest_pre_entry_low_speed_frames': best,
            'diagnostic_full_halt_span': best >= 20,
            'view_point_nearest_intersecting_highway_verified': False,
            'unmarked_crosswalk_absence_verified': False,
            'original_native_observed': source_kind == 'original_native',
            'physical_completion': False, 'legal_verdict': None}


def read_and_measure(path, source_kind):
    return measure([json.loads(line) for line in Path(path).read_text().splitlines()],
                   source_kind)
