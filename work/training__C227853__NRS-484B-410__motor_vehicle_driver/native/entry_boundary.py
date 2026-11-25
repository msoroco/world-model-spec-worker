"""Source-bound audit for an off-highway origin and highway entry crossing.

This is a CPU preparation component for a future eligible entry cell. It does
not classify whether a physical entry was safe under NRS 484B.410.
"""
import hashlib
import json
import math
from pathlib import Path


def _source(root, item, label):
    if not isinstance(item, dict) or not item.get('citation'):
        raise ValueError(label + ' citation missing')
    relative = item.get('path')
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(label + ' source path missing')
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError(label + ' source missing')
    if hashlib.sha256(path.read_bytes()).hexdigest() != item.get('sha256'):
        raise ValueError(label + ' source hash differs')
    return str(path)


def audit(manifest_path, trace_path):
    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('format') != 'nrs-484b-410-entry-boundary-v1':
        raise ValueError('Entry boundary manifest format missing')
    sources = manifest.get('sources')
    required = {'private_origin', 'public_highway', 'boundary', 'pre_movement_review'}
    if not isinstance(sources, dict) or set(sources) != required:
        raise ValueError('Entry boundary requires four independent sources')
    bound = {name: _source(root, sources[name], name) for name in sorted(required)}
    if manifest.get('state') != 'Nevada' or manifest.get('boundary_coordinate_system') != 'local_xy_m':
        raise ValueError('Nevada highway boundary identity missing')
    if manifest.get('review_conclusion') not in ('reviewed_safe', 'reviewed_unsafe', 'undetermined'):
        raise ValueError('Independent pre-movement review conclusion missing')
    if manifest.get('review_completed_before_movement') is not True:
        raise ValueError('Safety review must precede movement')
    trace_path = Path(trace_path).resolve()
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line]
    if len(rows) < 3 or [r.get('frame') for r in rows] != list(range(len(rows))):
        raise ValueError('Entry trace frame sequence missing')
    if any(type(r.get('native_frame')) is not int or type(r.get('time_s')) not in (int, float)
           or type(r.get('ego_origin_side')) is not bool or type(r.get('ego_highway_side')) is not bool
           for r in rows):
        raise ValueError('Original entry side observations missing')
    if any(type(r.get('ego_boundary_signed_distance_m')) not in (int, float)
           or not math.isfinite(r['ego_boundary_signed_distance_m'])
           or r['ego_origin_side'] != (r['ego_boundary_signed_distance_m'] < 0)
           or r['ego_highway_side'] != (r['ego_boundary_signed_distance_m'] >= 0)
           for r in rows):
        raise ValueError('Entry side differs from measured boundary distance')
    if any(b['native_frame'] <= a['native_frame'] or b['time_s'] <= a['time_s']
           for a, b in zip(rows, rows[1:])):
        raise ValueError('Entry time or Native frame is not increasing')
    if not rows[0]['ego_origin_side'] or rows[0]['ego_highway_side']:
        raise ValueError('Entry must begin off highway')
    crossings = [r for r in rows[1:] if r['ego_highway_side']]
    if not crossings or any(r['ego_origin_side'] and r['ego_highway_side'] for r in rows):
        raise ValueError('Highway boundary crossing not observed')
    first = crossings[0]
    if any(r['ego_highway_side'] for r in rows[:first['frame']]):
        raise ValueError('Entry boundary ordering differs')
    if not any(r.get('approaching_traffic_native_frame') == r['native_frame'] for r in rows):
        raise ValueError('Original approaching traffic join missing')
    if not any(r.get('ego_moving') is False for r in rows[:first['frame']]):
        raise ValueError('Pre-movement interval missing')
    return {'passed': True, 'first_highway_frame': first['frame'],
            'original_native_frame': first['native_frame'], 'bound_sources': bound,
            'review_conclusion': manifest['review_conclusion'],
            'legal_safety_decision_claimed': False, 'physical_entry_claimed': False}
