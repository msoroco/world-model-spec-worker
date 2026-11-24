"""Source-bound CPU diagnostic for yellow curb, sign hours and taxi standing."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    sources = json.loads((folder / 'sources.json').read_text())
    if sources.get('kind') != 'synthetic_cpu_yellow_curb':
        raise ValueError('Synthetic provenance differs')
    for name in ('zone.json', 'sign.json', 'taxi.jsonl'):
        if digest(folder / name) != sources['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    zone = json.loads((folder / 'zone.json').read_text())
    sign = json.loads((folder / 'sign.json').read_text())
    if zone != {'curb_color': 'yellow', 'x_range_m': [0.0, 20.0], 'y_range_m': [-1.0, 1.0]}:
        raise ValueError('Yellow zone geometry differs')
    if sign != {'kind': 'synthetic_posted_condition', 'start_local': '09:00', 'end_local': '17:00',
                'purpose': 'taxicab passenger waiting', 'timezone': 'America/Los_Angeles'}:
        raise ValueError('Posted sign source differs')
    rows = [json.loads(line) for line in (folder / 'taxi.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 Native frames')
    standing = in_zone = sign_active_standing = 0
    first_standing = last_standing = None
    first_civil = None
    for i, row in enumerate(rows):
        if row['frame'] != 1000 + i or abs(row['time_s'] - i / 20) > 1e-8:
            raise ValueError('Native frame/time join differs')
        if row.get('actor_kind') != 'taxicab':
            raise ValueError('Taxicab source missing')
        civil = datetime.fromisoformat(row['civil_time_local'])
        if first_civil is None:
            first_civil = civil
        if civil != first_civil + timedelta(seconds=i / 20):
            raise ValueError('Civil time join differs')
        stopped = row['speed_mps'] == 0
        inside = zone['x_range_m'][0] <= row['x_m'] <= zone['x_range_m'][1] and zone['y_range_m'][0] <= row['y_m'] <= zone['y_range_m'][1]
        active = sign['start_local'] <= civil.strftime('%H:%M') < sign['end_local']
        standing += stopped
        in_zone += stopped and inside
        sign_active_standing += stopped and inside and active
        if stopped:
            first_standing = row['frame'] if first_standing is None else first_standing
            last_standing = row['frame']
    return {'source_kind': sources['kind'], 'source_sha256': sources['sha256'],
            'frame_count': 600, 'rate_hz': 20, 'standing_frames': standing,
            'standing_in_yellow_zone_frames': in_zone, 'sign_active_standing_frames': sign_active_standing,
            'first_standing_frame': first_standing, 'last_standing_frame': last_standing,
            'passenger_waiting_purpose_verified': False, 'actual_sign_authority_verified': False,
            'outside_hours_ordinary_rule': 'unresolved', 'physical_native_verified': False,
            'legal_verdict_claimed': False}
