"""Source-bound synthetic rider/ego conflict timing, without a legal yield verdict."""
import hashlib
import json
import math
from pathlib import Path
from measure_facility import overlap_area, rectangle

RATE_HZ = 20
RIDERS = ('bicycle', 'electric_bicycle', 'electric_scooter')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(rows) != 480:
        raise ValueError('Expected 480 original frames')
    for index, row in enumerate(rows):
        if type(row.get('native_frame')) is not int or row['native_frame'] < 0:
            raise ValueError('Invalid original frame')
        if type(row.get('time_s')) not in (float, int) or not math.isfinite(row['time_s']):
            raise ValueError('Invalid original time')
        if index:
            prior = rows[index - 1]
            if row['native_frame'] != prior['native_frame'] + 1 or abs(row['time_s'] - prior['time_s'] - .05) > .002:
                raise ValueError('Original frame/time join failed')
        for actor in ('ego', 'rider'):
            speed = row.get(actor + '_speed_mps')
            if type(speed) not in (float, int) or not math.isfinite(speed) or speed < 0:
                raise ValueError('Invalid original speed')
            if row.get(actor + '_body_xy') is None:
                raise ValueError('Missing original body')
    return rows


def measure(samples_path, geometry_path, manifest_path):
    samples_path, geometry_path, manifest_path = map(Path, (samples_path, geometry_path, manifest_path))
    for path in (samples_path, geometry_path, manifest_path):
        if not path.is_file():
            raise ValueError('Missing original source ' + path.name)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('source_kind') != 'synthetic_native_shaped_diagnostic' or manifest.get('accepted') is not False:
        raise ValueError('Invalid source scope')
    if manifest.get('samples_sha256') != sha(samples_path) or manifest.get('geometry_sha256') != sha(geometry_path):
        raise ValueError('Changed original source bytes')
    geometry = json.loads(geometry_path.read_text())
    conflict = rectangle(geometry.get('conflict_native_xy_bounds_m'), 'conflict bounds')
    facility = rectangle(geometry.get('bicycle_facility_native_xy_bounds_m'), 'facility bounds')
    if not (facility[0] <= conflict[0] < conflict[2] <= facility[2] and
            facility[1] <= conflict[1] < conflict[3] <= facility[3]):
        raise ValueError('Conflict is outside facility')
    rider_type = manifest.get('rider_type')
    if rider_type not in RIDERS:
        raise ValueError('Unqualified rider type')
    rows = _rows(samples_path)
    if any(row.get('rider_type') != rider_type or row.get('rider_actor_id') != manifest.get('rider_actor_id')
           or row.get('rider_native_road_id') != geometry.get('rider_road_id')
           or row.get('rider_native_lane_id') != geometry.get('rider_lane_id')
           or row.get('ego_native_road_id') != geometry.get('ego_road_id') for row in rows):
        raise ValueError('Original actor or Native road/lane join failed')
    rider = [i for i, row in enumerate(rows) if overlap_area(row['rider_body_xy'], conflict) > .01]
    ego = [i for i, row in enumerate(rows) if overlap_area(row['ego_body_xy'], conflict) > .01]
    if not rider or not ego:
        raise ValueError('Missing observed conflict occupancy')
    if rider[0] >= ego[0]:
        raise ValueError('Rider did not arrive before ego')
    first_ego, last_rider = ego[0], rider[-1]
    simultaneous = len(set(rider) & set(ego))
    return {'format': 'c10052-rider-conflict-timing-v1',
            'rider_type': rider_type, 'rider_actor_id': manifest['rider_actor_id'],
            'first_rider_frame': rows[rider[0]]['native_frame'],
            'last_rider_frame': rows[last_rider]['native_frame'],
            'first_ego_frame': rows[first_ego]['native_frame'],
            'simultaneous_conflict_frames': simultaneous,
            'clearance_s': round((first_ego-last_rider)*.05, 6),
            'ego_entered_after_rider_cleared': first_ego > last_rider,
            'source_sha256': {'samples': sha(samples_path), 'geometry': sha(geometry_path),
                              'manifest': sha(manifest_path)},
            'source_scope': 'synthetic diagnostic; facility designation and legal priority unverified',
            'accepted': False}
