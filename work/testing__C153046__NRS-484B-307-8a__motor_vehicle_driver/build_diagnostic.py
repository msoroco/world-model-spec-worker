"""Build clearly synthetic red-left diagnostic sources for pinned compatibility."""
from __future__ import annotations

import hashlib
import base64
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / 'work/testing__C111125__NRS-484B-307-2a__motor_vehicle_driver/diagnostic-green_pedestrian_present.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def text(value) -> str:
    return json.dumps(value, sort_keys=True) + '\n'


def main() -> None:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    base = json.loads(BASE.read_text())
    base_trace = [json.loads(line) for line in base['files']['trace.jsonl'].splitlines()]
    base_map = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(ROOT.name + '__')
        direction = case['draft_variables']['receiving_direction']
        route = 'two_way_routes' if direction == 'two_way' else 'one_way_routes'
        sources = {}
        files = dict(base['files'])
        for name in ('opendrive', 'official_signal', route, 'stop_reference'):
            raw = ('synthetic red-left ' + name + ' source\n').encode()
            path = 'original-attempt/source-review/' + name + '.txt'
            files[path] = raw.decode()
            sources[name] = {'path': 'source-review/' + name + '.txt',
                             'sha256': sha(raw), 'citation': 'synthetic compatibility fixture',
                             'reviewer': 'fixture'}
        packet = {'format': 'c153046-red-left-site-v1', 'reviewer': 'fixture',
                  'sources': sources, 'approach_one_way': True,
                  'receiving_one_way_to_left': direction == 'one_way_left',
                  'receiving_two_way': direction == 'two_way',
                  'approach_direction_xy': [1, 0], 'receiving_direction_xy': [0, 1],
                  'approach_reference_xy': [0, 0],
                  'approach_lane_centers_xy': {'inner': [0, 0], 'left': [0, 3.5]},
                  'extreme_left_lane_id': 'left',
                  'signal': {'official': True, 'head_configuration': 'steady_red_alone',
                             'native_actor_id': 'fixture-signal'},
                  'stop_reference': {'kind': 'marked_crosswalk', 'hierarchy_reviewed': True,
                                     'point_xy': [101, 0]}}
        packet_raw = text(packet).encode()
        files['original-attempt/site-packet.json'] = packet_raw.decode()
        lane = 'inner' if case['draft_variables']['approach_position'] == 'inner_lane' else 'left'
        lateral = 0 if lane == 'inner' else 3.5
        history = []
        for index, point in enumerate(base_trace):
            frame = point['frame']; time_s = point['time_s']
            center = 98.0 + index * 0.1
            native = {'origin': 'native_world_snapshot', 'frame': frame,
                      'time_s': time_s, 'signal_actor_id': 'fixture-signal',
                      'signal_state': 'steady_red_alone',
                      'ego': {'lane_id': lane, 'speed_m_s': point['speed_mps'],
                              'body_vertices_xy': [[center-1, lateral-1],
                                                   [center+1, lateral-1],
                                                   [center+1, lateral+1],
                                                   [center-1, lateral+1]]},
                      'directed_participants': []}
            target = case['draft_variables']['conflict_response_request']
            if target.startswith(('pedestrian', 'traffic')):
                native['directed_participants'] = [{'kind': target.split('_')[0],
                    'native_actor_id': 'fixture-directed',
                    'source_citation': 'synthetic directed conflict fixture',
                    'conflict_zone_occupied': index in (4, 5)}]
            history.append({'case_id': case['case_id'],
                            'source_packet_sha256': sha(packet_raw),
                            'native_frame': native, 'camera_frames': {}})
        camera_hashes = {}
        for camera in CAMERAS:
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED) as stream:
                for index, row in enumerate(history):
                    raw = b'\x89PNG\r\n\x1a\n' + (camera + '-' + str(index)).encode()
                    frame = row['native_frame']['frame']
                    stream.writestr(f'{index:04d}-{frame}.png', raw)
                    row['camera_frames'][camera] = {'original_frame': frame,
                                                    'source_sha256': sha(raw)}
            archive_bytes = archive.getvalue()
            camera_hashes[camera] = sha(archive_bytes)
            files['original-attempt/' + camera + '.zip.b64'] = base64.b64encode(archive_bytes).decode() + '\n'
        history_raw = ''.join(text(row) for row in history)
        frame_map_raw = text({'frames': [{'video_frame': index,
                                          'frame': row['native_frame']['frame'],
                                          'time_s': row['native_frame']['time_s']}
                                         for index, row in enumerate(history)]})
        files['original-attempt/history.jsonl'] = history_raw
        files['original-attempt/frame-map.json'] = frame_map_raw
        inventory = {'case_id': case['case_id'], 'site_sha256': sha(packet_raw),
                     'history_sha256': sha(history_raw.encode()),
                     'frame_map_sha256': sha(frame_map_raw.encode()),
                     'camera_media_sha256': camera_hashes, 'original_frames': len(history),
                     'diagnostic_fixture': True, 'physical_acceptance_claimed': False}
        files['original-attempt/inventory.json'] = text(inventory)
        files['fixture-provenance.json'] = text({'diagnostic_fixture': True,
            'scope': 'synthetic red-left source measurement with generic conversion scaffold',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'frames': len(history)})
        files['trace.jsonl'] = ''.join(text(point) for point in base_trace)
        files['video_frames.jsonl'] = ''.join(text(point) for point in base_map)
        capture_manifest = json.loads(files['capture/manifest.json'])
        capture_manifest['case_id'] = case['case_id']
        capture_manifest['acquisition'] = 'synthetic_diagnostic_fixture'
        capture_manifest['source_run'] = 'fixture:red-left-software-compatibility'
        capture_manifest['sources']['trace.jsonl'] = sha(files['trace.jsonl'].encode())
        files['capture/manifest.json'] = text(capture_manifest)
        spec = {'files': files, 'graphs': base['graphs'], 'videos': base['videos']}
        spec_path = ROOT / f'diagnostic-{suffix}.json'
        spec_path.write_text(json.dumps(spec, sort_keys=True) + '\n')
        digest = sha(spec_path.read_bytes())
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': 'work/' + ROOT.name + '/' + spec_path.name,
                               'sha256': digest}],
                  'generator': {'source': 'work/' + ROOT.name + '/' + spec_path.name,
                                'sha256': digest}}
        (ROOT / f'diagnostic-{suffix}-recipe.json').write_text(json.dumps(recipe, indent=2,
                                                                sort_keys=True) + '\n')
        print('diagnostic fixture spec:', suffix, spec_path.stat().st_size, flush=True)


if __name__ == '__main__':
    main()
