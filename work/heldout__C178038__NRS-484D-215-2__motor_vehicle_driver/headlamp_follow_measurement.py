"""Original following distance and headlamp readback for NRS 484D.215(2).

The statute supplies 300 feet. This module measures the boundary and records
separately cited lighting-time context without deciding legal compliance.
"""

from hashlib import sha256
import json
from math import hypot
from pathlib import Path

from shapely.geometry import Polygon


METRES_PER_FOOT = 0.3048


def _rows(path, name):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    raw = path.read_bytes()
    try:
        return [json.loads(line) for line in raw.splitlines()], sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original ' + name) from error


def _point(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Missing original ' + label)
    return float(value[0]), float(value[1])


def _polygon(value, label):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Original ' + label + ' needs four corners')
    shape = Polygon([_point(point, label) for point in value])
    if not shape.is_valid or shape.area <= 0:
        raise ValueError('Degenerate original ' + label)
    return shape


def measure(footprint_path, lamp_path, context_path):
    footprints, footprint_sha = _rows(footprint_path, 'following_footprints.jsonl')
    lamps, lamp_sha = _rows(lamp_path, 'headlamp_readbacks.jsonl')
    context_path = Path(context_path)
    if not context_path.is_file() or not context_path.read_bytes():
        raise ValueError('Missing required source: lighting_context.json')
    context_raw = context_path.read_bytes()
    context = json.loads(context_raw)
    if type(context.get('lighting_time_applies')) is not bool or not context.get('time_source'):
        raise ValueError('Lighting-time premise needs a cited source')
    if len(footprints) < 2 or len(lamps) != len(footprints):
        raise ValueError('Original following/lamp frame count differs')
    ego_id, lead_id = footprints[0].get('ego_id'), footprints[0].get('lead_id')
    if not ego_id or not lead_id or ego_id == lead_id:
        raise ValueError('Original following actor identities missing')
    observations = []
    previous = None
    for footprint, lamp in zip(footprints, lamps):
        if footprint.get('ego_id') != ego_id or footprint.get('lead_id') != lead_id:
            raise ValueError('Following actor identity changed')
        frame, time_s = footprint.get('frame'), footprint.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float):
            raise ValueError('Original following frame/time missing')
        if (lamp.get('frame'), lamp.get('time_s')) != (frame, time_s):
            raise ValueError('Original lamp/footprint frame join failed')
        if previous and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original following samples are not 20 Hz')
        previous = frame, time_s
        if (type(lamp.get('uppermost_distribution')) is not bool or
                type(lamp.get('low_beam_readback')) is not bool):
            raise ValueError('Both high and low beam states need Native readback')
        ego, lead = _polygon(footprint.get('ego_corners_xy'), 'ego footprint'), _polygon(footprint.get('lead_corners_xy'), 'lead footprint')
        hx, hy = _point(footprint.get('ego_heading_xy'), 'ego heading')
        lx, ly = _point(footprint.get('lead_heading_xy'), 'lead heading')
        hn, ln = hypot(hx, hy), hypot(lx, ly)
        if min(hn, ln) < 1e-6:
            raise ValueError('Original following heading degenerate')
        aligned = (hx * lx + hy * ly) / hn / ln > .98
        dx, dy = lead.centroid.x - ego.centroid.x, lead.centroid.y - ego.centroid.y
        ahead = (dx * hx + dy * hy) > 0
        gap_ft = ego.distance(lead) / METRES_PER_FOOT
        observations.append({'frame': frame, 'time_s': time_s,
                             'surface_gap_ft': gap_ft,
                             'same_direction': aligned,
                             'lead_ahead': ahead,
                             'following_geometry': aligned and ahead,
                             'below_300ft': gap_ft < 300,
                             'at_300ft': abs(gap_ft - 300) < 1e-7,
                             'uppermost_distribution_readback': lamp['uppermost_distribution'],
                             'low_beam_readback': lamp['low_beam_readback'],
                             'no_beam_readback': not (lamp['uppermost_distribution'] or
                                                      lamp['low_beam_readback'])})
    return {'format': 'worker-following-headlamp-observation',
            'sources': {'following_footprints.jsonl': footprint_sha,
                        'headlamp_readbacks.jsonl': lamp_sha,
                        'lighting_context.json': sha256(context_raw).hexdigest()},
            'ego_id': ego_id, 'lead_id': lead_id,
            'lighting_time_source': context['time_source'],
            'lighting_time_applies': context['lighting_time_applies'],
            'minimum_surface_gap_ft': min(row['surface_gap_ft'] for row in observations),
            'observations': observations,
            'legal_headlamp_judgment': None,
            'safe_distance_judgment': None}
