"""Case-specific synthetic inputs for pinned compatibility, never original facts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fire_lane import CASES
from source_packet import SOURCES, EXCEPTION_SOURCES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
TRACE = [json.loads(line) for line in BASE['files']['trace.jsonl'].splitlines() if line]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def serial(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'


def build(case) -> None:
    case_id = ROOT.name + '__' + case.id
    spec = {'files': dict(BASE['files']), 'graphs': BASE['graphs'],
            'videos': BASE['videos']}
    files = spec['files']
    for old in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
        files.pop(old, None)
    files['fixture-provenance.json'] = serial({
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
        'scope': 'synthetic fire-lane software exercise only', 'case_id': case_id})
    site = {'cell_id': 'C150099', 'layout': 'one_way_road',
            'property_kind': case.property_kind, 'sign_support': 'spawned_prop',
            'sign_text': 'FIRE LANE', 'posted_interval_m': [10, 30],
            'curb_y_m': 2, 'approach_waypoints': [[0, 0], [40, 0]],
            'conflict_actor_waypoints': [[3, 0], [38, 0]]}
    names = list(SOURCES)
    if case.exception != 'none':
        names.append(EXCEPTION_SOURCES[case.exception])
    for name in names:
        source = ('DIAGNOSTIC ONLY shared one-way site ' + name + '\n').encode()
        files['original-attempt/source-review/' + name + '.txt'] = source.decode()
        site[name + '_sha256'] = sha(source)
    site_text = serial(site)
    files['original-attempt/site.json'] = site_text
    site_sha = sha(site_text.encode())
    frame_map = {'frames': [{'frame': row['frame'], 'time_s': row['time_s'],
                             'video_frame': index} for index, row in enumerate(TRACE)]}
    frame_map_text = serial(frame_map)
    files['original-attempt/frame_map.json'] = frame_map_text
    frame_map_sha = sha(frame_map_text.encode())
    hold_state = {'park': 'parked', 'stand': 'standing', 'stop': 'stopped'}[case.activity]
    history = []
    for row in TRACE:
        frame = row['frame']
        if case.sweep_kind == 'posted_offset':
            centre = site['posted_interval_m'][1] + case.sweep_setpoint_m
            body = [centre - 2, centre + 2]
        else:
            body = [11, 15] if case.target_region == 'inside' else [31, 35]
        history.append({
            'case_id': case_id, 'original_frame': frame,
            'time_s': row['time_s'], 'ego_id': 'diagnostic-ego',
            'sign_id': 'diagnostic-sign', 'site_sha256': site_sha,
            'frame_map_sha256': frame_map_sha,
            'source_sha256': sha(serial(row).encode()),
            'body_footprint_source_sha256': sha(serial(body).encode()),
            'sign_physically_present': True, 'sign_text_readback': 'FIRE LANE',
            'body_west_x_m': body[0], 'body_east_x_m': body[1],
            'body_curb_gap_m': .2, 'body_interval_m': body,
            'posted_interval_m': site['posted_interval_m'],
            'activity_observation': hold_state,
            'attended_observation': case.attended,
            'property_kind': case.property_kind,
            'exception_kind': case.exception,
            'exception_source_sha256': site.get(EXCEPTION_SOURCES.get(case.exception, '') + '_sha256'),
            **({'reviewed_posted_end_x_m': site['posted_interval_m'][1]}
               if case.sweep_kind == 'posted_offset' else {}),
            **({'actual_actor_body_gap_m': case.sweep_setpoint_m,
                'conflict_actor_id': 'diagnostic-conflict-actor',
                'traffic_conflict_source_sha256': site['traffic_conflict_source_sha256']}
               if case.sweep_kind == 'conflict_gap' else {}),
            'camera_frames': {name: {'original_frame': frame,
                'source_sha256': sha(f'DIAGNOSTIC ONLY {name} {frame}\n'.encode())}
                for name in ('overview', 'approach', 'reference_corner',
                             'driver_reference')},
            **{key: site[key] for key in (
                'map_sha256', 'jurisdiction_sha256',
                'fire_code_designation_sha256', 'posting_authority_sha256',
                'posted_extent_sha256', 'sign_identity_sha256',
                'sign_appearance_sha256', 'curb_geometry_sha256',
                'property_source_sha256', 'route_sha256', 'weather_sha256',
                'camera_plan_sha256')},
        })
    history_text = ''.join(serial(row) for row in history)
    files['original-attempt/history.jsonl'] = history_text
    files['original-attempt/inventory.json'] = serial({
        'case_id': case_id, 'source_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'site_sha256': site_sha,
        'history_sha256': sha(history_text.encode()),
        'frame_map_sha256': frame_map_sha, 'physical_completion': False})
    spec_path = ROOT / ('diagnostic-' + case.id + '.json')
    raw = (json.dumps(spec, separators=(',', ':'), sort_keys=True) + '\n').encode()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('diagnostic input exceeds return limit')
    spec_path.write_bytes(raw)
    recipe = {
        'format': 'worker-fixture-recipe',
        'generator': {'source': f'work/{ROOT.name}/{spec_path.name}',
                      'sha256': sha(raw)},
        'sources': [{'path': 'diagnostic-input.json',
                     'source': f'work/{ROOT.name}/{spec_path.name}',
                     'sha256': sha(raw)}],
    }
    (ROOT / ('diagnostic-' + case.id + '-recipe.json')).write_text(
        json.dumps(recipe, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    for case in CASES:
        build(case)
    print('case-specific synthetic recipes:', len(CASES))
