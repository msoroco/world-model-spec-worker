"""Create UTF-8 synthetic source specs for pinned four-view compatibility."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / 'work/testing__C111125__NRS-484B-307-2a__motor_vehicle_driver/diagnostic-green_pedestrian_present.json'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('map_opendrive', 'jurisdiction', 'intersection_geometry',
           'non_through_classification', 'all_entrance_controls', 'ego_stop_sign',
           'stop_reference', 'ego_route', 'ego_vehicle', 'other_route',
           'other_obligation', 'through_vehicle_exemption', 'sightlines',
           'officer_control', 'signal_control')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def text(value):
    return json.dumps(value, sort_keys=True) + '\n'


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    base = json.loads(BASE.read_text())
    trace = [json.loads(line) for line in base['files']['trace.jsonl'].splitlines()]
    frame_map = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    if len(trace) < 8 or len(trace) > 20:
        raise ValueError('synthetic scaffold frame count unsupported')
    speed = json.loads((ROOT / 'speed-sweep-extension.json').read_text()) if (ROOT / 'speed-sweep-extension.json').exists() else {'cases': []}
    speed_cases = [{**row['draft_variables'], 'case_id': row['case_id']}
                   for row in speed['cases']]
    cases = {case['case_id']: case for case in plan['cases']}
    cases.update({case['case_id']: case for case in speed_cases})
    for case in cases.values():
        suffix = case['case_id'].removeprefix(ROOT.name + '__')
        files = dict(base['files'])
        sources = {}
        for name in SOURCES:
            raw = ('synthetic non-through stop ' + name + '\n').encode()
            files['original-attempt/source-review/' + name + '.txt'] = raw.decode()
            sources[name] = {'path': 'source-review/' + name + '.txt',
                             'sha256': sha(raw)}
        spec = lambda x: {'blueprint_id': 'vehicle.fixture',
                          'source_citation': 'synthetic fixture',
                          'route_source_citation': 'synthetic fixture',
                          'location_xyz_m': [x, 0, 0],
                          'rotation_rpy_deg': [0, 0, 0],
                          'route_points_xyz_m': [[x, 0, 0], [x + 20, 0, 0]],
                          'initial_station_m': x}
        site = {'format': 'c158190-reviewed-native-site-v1',
                'cell_id': plan['cell_id'], 'law_id': plan['law_id'],
                'actor': plan['actor'], 'case_id': case['case_id'],
                'sources': sources, 'non_through_highway': True,
                'ego_stop_sign_present': True,
                'other_obligated_to_stop_or_yield': False,
                'officer_controls': False, 'signal_controls': False,
                'entrances': [{'id': 'west', 'control': 'stop',
                               'reviewed_source': 'synthetic fixture'},
                              {'id': 'north', 'control': 'none',
                               'reviewed_source': 'synthetic fixture'}],
                'ego_entrance_id': 'west', 'other_entrance_id': 'north',
                'stop_reference_station_m': -2,
                'intersection_entry_station_m': 1,
                'intersection_polygon_source': 'synthetic fixture',
                'ego_route_continuity_review': True,
                'other_route_continuity_review': True,
                'spawn_plan': {'ego': spec(-10), 'other': spec(3)}}
        site_raw = text(site)
        files['original-attempt/site-packet.json'] = site_raw
        rows = []
        source_hashes = {name: sources['map_opendrive']['sha256']
                         for name in ('source', 'ego_motion', 'other_motion',
                                      'body_geometry', 'controls', 'sightlines',
                                      'entrance_controls')}
        for index, point in enumerate(trace):
            frame = point['frame']
            time_s = point['time_s']
            station = -3 if index < 4 else 2 + .1 * (index - 4)
            native = {'ego_id': 'fixture-ego', 'other_id': 'fixture-other',
                      'other_obligated_to_stop_or_yield': False,
                      'officer_controls': False, 'signal_controls': False,
                      'ego_speed_mps': 3.5 if index < 4 or
                      case['approach_policy'] == 'uninterrupted' else 0.0,
                      'ego_leading_station_m': station,
                      'other_center_station_m': case['requested_other_station_m'] - .1 * index,
                      'other_min_vertex_station_m': case['requested_other_station_m'] - 2 - .1 * index,
                      'other_phase': case['through_phase'],
                      'ego_across_or_within': index >= 4,
                      'ego_full_body_overlap': 4 <= index <= 6,
                      'ego_full_body_cleared': index >= 7,
                      'traffic_reference_event': index == 3,
                      'source_hashes': source_hashes}
            rows.append({'case_id': case['case_id'],
                         'source_packet_sha256': sha(site_raw.encode()),
                         'original_frame': frame, 'time_s': time_s,
                         'native_state': native, 'camera_frames': {}})
        camera_hashes = {}
        for camera in VIEWS:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as archive:
                for index, row in enumerate(rows):
                    raw = b'\x89PNG\r\n\x1a\n' + (camera + '-' + str(index)).encode()
                    member = f'{index:04d}-{row["original_frame"]}.png'
                    archive.writestr(member, raw)
                    row['camera_frames'][camera] = {'source_sha256': sha(raw),
                                                     'archive_member': member}
            media = buffer.getvalue()
            camera_hashes[camera] = sha(media)
            files['original-attempt/' + camera + '.zip.b64'] = base64.b64encode(media).decode() + '\n'
        history = ''.join(text(row) for row in rows)
        mapping = text({'case_id': case['case_id'], 'frames': [
            {'video_frame': index, 'frame': row['original_frame'],
             'time_s': row['time_s']} for index, row in enumerate(rows)]})
        files['original-attempt/history.jsonl'] = history
        files['original-attempt/frame-map.json'] = mapping
        files['original-attempt/inventory.json'] = text({
            'case_id': case['case_id'], 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False,
            'site_sha256': sha(site_raw.encode()), 'history_sha256': sha(history.encode()),
            'frame_map_sha256': sha(mapping.encode()),
            'camera_media_sha256': camera_hashes})
        files['fixture-provenance.json'] = text({'diagnostic_fixture': True,
            'scope': 'synthetic non-through stop software compatibility',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'frames': len(rows)})
        files['trace.jsonl'] = ''.join(text(point) for point in trace)
        files['video_frames.jsonl'] = ''.join(text(point) for point in frame_map)
        capture_manifest = json.loads(files['capture/manifest.json'])
        capture_manifest['case_id'] = case['case_id']
        capture_manifest['acquisition'] = 'synthetic_diagnostic_fixture'
        capture_manifest['source_run'] = 'fixture:nonthrough-yield-software-compatibility'
        capture_manifest['sources']['trace.jsonl'] = sha(files['trace.jsonl'].encode())
        files['capture/manifest.json'] = text(capture_manifest)
        diagnostic = {'files': files, 'graphs': base['graphs'], 'videos': base['videos']}
        diagnostic_path = ROOT / f'diagnostic-{suffix}.json'
        diagnostic_path.write_text(json.dumps(diagnostic, sort_keys=True) + '\n')
        digest = sha(diagnostic_path.read_bytes())
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': 'work/' + ROOT.name + '/' + diagnostic_path.name,
                               'sha256': digest}],
                  'generator': {'source': 'work/' + ROOT.name + '/' + diagnostic_path.name,
                                'sha256': digest}}
        (ROOT / f'diagnostic-{suffix}-recipe.json').write_text(
            json.dumps(recipe, indent=2, sort_keys=True) + '\n')
        print('diagnostic UTF-8 source spec:', suffix, diagnostic_path.stat().st_size)


if __name__ == '__main__':
    main()
