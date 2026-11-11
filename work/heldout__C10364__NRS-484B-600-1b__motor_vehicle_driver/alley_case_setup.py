"""Exact C10364 alley engineering settings; no legal speed boundary."""

from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from alley_geometry import Point, plan_alley


PREFIX = 'heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver__'
CASES = {f'{kind}_{speed}mps': (kind, float(speed))
         for kind in ('person', 'property') for speed in (3, 5, 7)}


def case_settings(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-600-1b', 'C10364', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact alley case identity')
    case_id = config.get('selected_case_id', '')
    suffix = case_id[len(PREFIX):] if case_id.startswith(PREFIX) else None
    if suffix not in CASES:
        raise ValueError('Unknown exact alley case')
    kind, speed = CASES[suffix]
    if (config.get('protected_interest'), config.get('target_speed_mps')) != (kind, speed):
        raise ValueError('Alley case interest or engineering speed differs')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 160, 8):
        raise ValueError('Alley case requires 160 frames at 20 Hz over eight seconds')
    if config.get('construction_probe_only') is not True:
        raise ValueError('Alley construction cannot masquerade as delivery')
    direction = config.get('alley_direction')
    if direction not in ('east', 'west'):
        raise ValueError('Alley route direction missing')
    polygon = config.get('alley_polygon_xy')
    if (not isinstance(polygon, list) or len(polygon) < 4 or
            any(not isinstance(point, list) or len(point) != 2 or
                any(type(value) not in (int, float) or not isfinite(value)
                    for value in point) for point in polygon)):
        raise ValueError('Alley polygon points missing')
    source = config.get('alley_polygon_source', {})
    if (not isinstance(source, dict) or not source.get('path') or
            not isinstance(source.get('sha256'), str) or len(source['sha256']) != 64):
        raise ValueError('Alley polygon needs a named, hashed source')
    source_path = Path(source['path'])
    if source_path.is_absolute() or '..' in source_path.parts:
        raise ValueError('Alley polygon source must be inside the attempt')
    width = config.get('alley_width_m')
    if type(width) not in (int, float) or not isfinite(width) or width < 5:
        raise ValueError('Alley participant layout needs at least five metres width')
    return {'case_id': case_id, 'protected_interest': kind,
            'speed_mps': speed, 'direction': direction,
            'polygon_xy': polygon, 'polygon_source': source,
            'alley_width_m': width}


def verify_polygon_source(settings, root):
    """Require the supplied map/annotation source bytes before Native selection."""
    source = settings['polygon_source']
    path = Path(root) / source['path']
    if not path.is_file() or sha256(path.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('Alley polygon source missing or changed')
    try:
        geometry = json.loads(path.read_text())
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError('Alley polygon source is not a geometry record') from error
    if geometry.get('polygon_xy') != settings['polygon_xy']:
        raise ValueError('Selected alley polygon differs from its source geometry')
    return path


def participant_positions(route, *, alley_width_m, vehicle_width_m=1.8):
    start = route[0].transform.location
    end = route[12].transform.location
    return plan_alley(Point(start.x, start.y), Point(end.x, end.y),
                      alley_width=alley_width_m,
                      vehicle_width=vehicle_width_m,
                      pedestrian_station=10.0, pedestrian_offset=1.8,
                      property_station=15.0, property_offset=-1.9)
