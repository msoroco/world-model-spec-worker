"""Read retained diagnostic sources for LVMC 11.30.140(B); make no legal finding."""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
SOURCES = ('road.json', 'pedestrian.json', 'frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def measure(folder):
    folder = Path(folder)
    manifest = read(folder / 'source-manifest.json')
    require(manifest.get('format') == 'c129273-retained-sources-v1', 'source manifest format')
    require(manifest.get('sha256') == {name: sha(folder / name) for name in SOURCES},
            'source hash mismatch')
    road = read(folder / 'road.json')
    person = read(folder / 'pedestrian.json')
    require(road.get('cell_id') == 'C129273' and road.get('layout') == 'mountain_road'
            and road.get('maneuver') == 'travel' and road.get('control') == 'blind_pedestrian'
            and road.get('ego_lane_y_m') == 0.0 and road.get('pedestrian_x_m') == 50.0,
            'fixed road/cell geometry')
    require(person.get('person_id') == 202 and person.get('blindness') in ('wholly', 'partially')
            and person.get('marker') in ('white_cane', 'white_red_tipped_cane', 'assisted_person')
            and person.get('marker_source') == 'synthetic_native_sample',
            'person identity/blindness/marker source')
    rows = [json.loads(line) for line in (folder / 'frames.jsonl').read_text().splitlines()]
    require(len(rows) == FRAMES, '600 source frames required')
    first_seen = first_deceleration = first_stop = first_release = first_contact = None
    first_sustained_stop = None
    stop_run = longest_stop_run = 0
    near_while_stopped = 0
    min_gap_before_release = math.inf
    min_ttc_before_release = math.inf
    previous_x = None
    previous_speed = None
    for i, row in enumerate(rows):
        require(row.get('frame') == i and row.get('native_frame') == i + 1000
                and type(row.get('time_s')) in (int, float)
                and abs(row['time_s'] - i / RATE_HZ) < 1e-9
                and row.get('ego_id') == 101 and row.get('ego_role') == 'motor_vehicle_driver'
                and row.get('person_id') == person['person_id'],
                f'frame/time/actor join {i}')
        x, speed, ped_y = row.get('ego_front_x_m'), row.get('ego_speed_mps'), row.get('person_y_m')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in (x, speed, ped_y))
                and speed >= 0 and abs(ped_y) <= 6,
                f'finite body motion {i}')
        require(type(row.get('person_marker_observed')) is bool,
                f'person marker observation {i}')
        if previous_x is not None:
            require(abs((x - previous_x) - speed / RATE_HZ) < 1e-5,
                    f'ego displacement/speed continuity {i}')
            require(abs(speed - previous_speed) <= 0.22,
                    f'ego acceleration continuity {i}')
        previous_x, previous_speed = x, speed
        if row['person_marker_observed'] and first_seen is None:
            first_seen = i
        if first_seen is not None and first_deceleration is None and speed < 7.9:
            first_deceleration = i
        gap = road['pedestrian_x_m'] - x - 0.5
        lateral_conflict = abs(ped_y - road['ego_lane_y_m']) <= 1.0
        if first_seen is not None and first_stop is None and speed <= 0.05 and gap > 0:
            first_stop = i
        if first_seen is not None and speed <= 0.05 and gap > 0:
            stop_run += 1
            longest_stop_run = max(longest_stop_run, stop_run)
            if stop_run == RATE_HZ and first_sustained_stop is None:
                first_sustained_stop = i - RATE_HZ + 1
        else:
            stop_run = 0
        if first_stop is not None and first_release is None and i > first_stop and speed > 0.05:
            first_release = i
        if first_stop is not None and first_release is None:
            min_gap_before_release = min(min_gap_before_release, gap)
            if lateral_conflict:
                near_while_stopped += 1
        if lateral_conflict and gap <= 0 and first_contact is None:
            first_contact = i
        if lateral_conflict and gap > 0 and speed > 0:
            ttc = gap / speed
            min_ttc_before_release = min(min_ttc_before_release, ttc)
    require(first_seen is not None, 'blind-person marker never observed')
    release_person_y = rows[first_release]['person_y_m'] if first_release is not None else None
    return {
        'format': 'c129273-blind-person-measurement-v1',
        'frames': FRAMES, 'rate_hz': RATE_HZ, 'duration_s': FRAMES / RATE_HZ,
        'person_marker': person['marker'], 'blindness': person['blindness'],
        'first_marker_observed_frame': first_seen,
        'first_deceleration_frame': first_deceleration,
        'first_full_stop_frame': first_stop,
        'first_sustained_full_stop_frame': first_sustained_stop,
        'longest_full_stop_run_frames': longest_stop_run,
        'first_post_stop_release_frame': first_release,
        'first_geometric_contact_frame': first_contact,
        'release_person_y_m': release_person_y,
        'conflict_frames_while_stopped': near_while_stopped,
        'minimum_surface_gap_before_release_m': None if math.isinf(min_gap_before_release) else round(min_gap_before_release, 5),
        'minimum_time_to_conflict_s': None if math.isinf(min_ttc_before_release) else round(min_ttc_before_release, 5),
        'reaction_to_deceleration_s': None if first_deceleration is None else round((first_deceleration-first_seen)/RATE_HZ, 5),
        'marker_source': person['marker_source'],
        'source_sha256': manifest['sha256'],
        'original_native_observed': False, 'physical_collision_claimed': False,
        'legal_verdict_claimed': False,
    }
