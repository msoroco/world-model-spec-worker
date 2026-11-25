"""Generate six explicit UTF-8 synthetic source specs for CPU compatibility."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

from speed_site import FIELD, REQUIRED

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / 'work/testing__C111125__NRS-484B-307-2a__motor_vehicle_driver/diagnostic-green_pedestrian_present.json'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def text(data):
    return json.dumps(data, sort_keys=True) + '\n'


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    base = json.loads(BASE.read_text())
    original_trace = [json.loads(line) for line in base['files']['trace.jsonl'].splitlines()]
    original_video = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    count = len(original_trace)
    if not 8 <= count <= 20 or len(original_video) != count:
        raise ValueError('diagnostic scaffold frame count unsupported')
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(ROOT.name + '__')
        variables = case['draft_variables']
        files = dict(base['files'])
        sources = {}
        for name in REQUIRED:
            raw = ('synthetic speed-zone ' + name + '\n').encode()
            files['original-attempt/source-review/' + name + '.txt'] = raw.decode()
            sources[name] = {'path': 'source-review/' + name + '.txt', 'sha256': sha(raw)}
        site = {'cell_id': 'C136559', 'layout': 'narrow_road',
                'authorized_speed_mph': 25.0,
                'vehicle_class': 'self_propelled_nonrail_motor_vehicle',
                'vehicle_class_source_sha256': sources['vehicle_classification']['sha256'],
                'lanes': {'eastbound': {'lane_id': 'diagnostic-east',
                                      'source_sha256': sources['eastbound_lane']['sha256'],
                                      'waypoints': [[0, 0, 0], [100, 0, 0]]},
                          'westbound': {'lane_id': 'diagnostic-west',
                                      'source_sha256': sources['westbound_lane']['sha256'],
                                      'waypoints': [[100, 3, 0], [0, 3, 0]]}},
                'signs': {'eastbound': {'source_sha256': sources['eastbound_sign']['sha256']},
                          'westbound': {'source_sha256': sources['westbound_sign']['sha256']}}}
        for name, field in FIELD.items():
            site[field] = sources[name]['sha256']
        packet = {'format': 'c136559-reviewed-speed-site-v1',
                  'cell_id': 'C136559', 'law_id': 'NRS-484B-620-2',
                  'actor': 'motor_vehicle_driver', 'case_id': case['case_id'],
                  'sources': sources, 'site': site}
        site_raw = text(packet)
        files['original-attempt/site-packet.json'] = site_raw
        trace = []
        video = []
        rows = []
        mapping = []
        for index, (point, frame) in enumerate(zip(original_trace, original_video)):
            original_frame = point['frame']
            t = point['time_s']
            point.update(original_frame=original_frame)
            frame.update(original_frame=original_frame, video_frame=index, time_s=t)
            trace.append(point)
            video.append(frame)
            rows.append({'original_frame': original_frame, 'original_time_s': t,
                         'source_sha256': sha(site_raw.encode()),
                         'zone_establishment_source_sha256': site['zone_establishment_source_sha256'],
                         'zone_extent_source_sha256': site['zone_extent_source_sha256'],
                         'sign_readback_source_sha256': sources[variables['direction'] + '_sign']['sha256'],
                         'map_source_sha256': site['road_source_sha256'],
                         'ego_id': 'diagnostic-ego',
                         'vehicle_class': site['vehicle_class'],
                         'direction': variables['direction'],
                         'sign_direction': variables['direction'],
                         'actual_speed_mps': variables['requested_mph'] * .44704,
                         'inside_zone': variables['zone_mode'] != 'outside',
                         'sign_installed': variables['zone_mode'] != 'sign_absent'})
            mapping.append({'video_frame': index, 'original_frame': original_frame,
                            'time_s': t, 'camera_frames': {}})
        for name in VIEWS:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as archive:
                for index in range(count):
                    raw = b'\x89PNG\r\n\x1a\n' + (name + '-' + str(index)).encode()
                    member = f'{index:04d}.png'
                    archive.writestr(member, raw)
                    mapping[index]['camera_frames'][name] = {'member': member, 'sha256': sha(raw)}
            files['original-attempt/' + name + '.zip.b64'] = base64.b64encode(buffer.getvalue()).decode() + '\n'
        capture = {'case_id': case['case_id'], 'cell_id': 'C136559',
                   'law_id': 'NRS-484B-620-2', 'authorized_speed_mph': 25.0,
                   'map_source_sha256': site['road_source_sha256'],
                   'zone_establishment_source_sha256': site['zone_establishment_source_sha256'],
                   'zone_extent_source_sha256': site['zone_extent_source_sha256'],
                   'sign_instruction_source_sha256': site['sign_instruction_source_sha256'],
                   'camera_plan_sha256': sha(text(json.loads((ROOT / 'config.json').read_text())['cameras']).encode()),
                   'ego_blueprint': 'vehicle.diagnostic', 'original_rows': rows,
                   'diagnostic_fixture': True}
        capture_raw = text(capture)
        files['original-attempt/capture.json'] = capture_raw
        files['original-attempt/capture-source-seal.json'] = text({
            'case_id': case['case_id'], 'capture_sha256': sha(capture_raw.encode())})
        files['original-attempt/frame-map.json'] = text({'case_id': case['case_id'], 'frames': mapping})
        files['trace.jsonl'] = ''.join(text(row) for row in trace)
        files['video_frames.jsonl'] = ''.join(text(row) for row in video)
        files['fixture-provenance.json'] = text({'diagnostic_fixture': True,
            'scope': 'synthetic speed-zone software compatibility',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'frames': count})
        capture_manifest = json.loads(files['capture/manifest.json'])
        capture_manifest.update(case_id=case['case_id'],
                                acquisition='synthetic_diagnostic_fixture',
                                source_run='fixture:speed-zone-software-compatibility')
        capture_manifest['sources']['trace.jsonl'] = sha(files['trace.jsonl'].encode())
        files['capture/manifest.json'] = text(capture_manifest)
        diagnostic = {'files': files, 'graphs': base['graphs'], 'videos': base['videos']}
        path = ROOT / ('diagnostic-' + suffix + '.json')
        path.write_text(json.dumps(diagnostic, sort_keys=True) + '\n')
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('diagnostic source exceeds returned-file limit')
        digest = sha(path.read_bytes())
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': 'work/' + ROOT.name + '/' + path.name,
                               'sha256': digest}],
                  'generator': {'source': 'work/' + ROOT.name + '/' + path.name,
                                'sha256': digest}}
        (ROOT / ('diagnostic-' + suffix + '-recipe.json')).write_text(
            json.dumps(recipe, indent=2, sort_keys=True) + '\n')
        print('diagnostic UTF-8 source spec:', suffix, path.stat().st_size)


if __name__ == '__main__':
    main()
