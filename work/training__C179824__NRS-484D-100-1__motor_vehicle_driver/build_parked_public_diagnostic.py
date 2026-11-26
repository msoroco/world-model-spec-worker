"""Build synthetic source fixtures for the two parked exception cases."""
import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
REVIEW_SOURCES = {
    'highway_source_sha256': 'highway-review.json',
    'vehicle_class_source_sha256': 'vehicle-class-review.json',
    'device_content_source_sha256': 'device-content-review.json',
    'device_authority_source_sha256': 'device-authority-review.json',
    'device_placement_source_sha256': 'device-placement-review.json',
    'device_timing_source_sha256': 'device-timing-review.json',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def lines(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True, separators=(',', ':'))+'\n'
                            for row in rows))


def one(suffix):
    case_id = ASSIGNMENT+'__'+suffix
    base = HERE/'cases'/('full_controlled_'+suffix[-1])
    target = HERE/'cases'/suffix
    source = target/'source'
    source.mkdir(parents=True, exist_ok=True)
    for path in (base/'source').rglob('*'):
        if path.is_file():
            output = source/path.relative_to(base/'source')
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output)
    vis = [json.loads(line) for line in (source/'visibility-trace.jsonl').read_text().splitlines()]
    lamp = [json.loads(line) for line in (source/'vehicle-lamps.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (source/'capture/evidence.jsonl').read_text().splitlines()]
    parked = []
    for i, (v, l, e) in enumerate(zip(vis, lamp, evidence)):
        if i >= 500:
            v['ego_speed_mps'] = 0.0
            v['ego_xy_m'][1] = -4.75
            l['speed_mps'] = 0.0
            l['vehicle_xy_m'][1] = -4.75
            e['ego']['position_m'][1] = -4.75
            e['ego']['speed_mps'] = 0.0
            e['world']['road_projection']['lane_id'] = -2
            for vertex in e['ego']['body_vertices_m']:
                vertex[1] -= 3.0
        parked.append({'source_kind': 'synthetic_diagnostic',
                       'video_frame': i, 'native_frame': l['native_frame'],
                       'time_s': l['time_s'], 'speed_mps': l['speed_mps'],
                       'road_id': l['road_id'],
                       'ego_xy_m': v['ego_xy_m'],
                       'shoulder_lane_id': -2 if i >= 500 else -1,
                       'on_shoulder_readback': i >= 500,
                       'native_light_state_bits': l['native_light_state_bits'],
                       'camera_native_frames': l['camera_native_frames']})
    lines(source/'visibility-trace.jsonl', vis)
    lines(source/'vehicle-lamps.jsonl', lamp)
    lines(source/'capture/evidence.jsonl', evidence)
    lines(source/'parked-trace.jsonl', parked)
    trace = []
    for item in vis:
        xy = item['ego_xy_m']
        trace.append({'frame': item['native_frame'], 'time_s': item['time_s'],
                      'position': {'x': xy[0], 'y': xy[1], 'z': 0},
                      'position_m': [xy[0], xy[1], 0], 'heading_deg': 0,
                      'speed_mps': item['ego_speed_mps'],
                      'speed_mph': item['ego_speed_mps']/.44704,
                      'velocity_mps': [item['ego_speed_mps'], 0, 0],
                      'control': {}})
    (source/'trace.jsonl').write_text(''.join(json.dumps(row, allow_nan=False)+'\n'
                                             for row in trace))
    pixel = json.loads((source/'visibility-pixel-review.json').read_text())
    pixel['trace_sha256'] = sha(source/'visibility-trace.jsonl')
    write(source/'visibility-pixel-review.json', pixel)
    for name in REVIEW_SOURCES.values():
        value = json.loads((source/name).read_text())
        value['case_id'] = case_id
        write(source/name, value)
    lamp_review = json.loads((source/'lamp-source-review.json').read_text())
    lamp_review['case_id'] = case_id
    for field, name in REVIEW_SOURCES.items():
        lamp_review[field] = sha(source/name)
    write(source/'lamp-source-review.json', lamp_review)
    for name in ('nrs-484d-165-source.json', 'parked-highway-review.json',
                 'parked-status-review.json'):
        write(source/name, {'case_id': case_id,
                            'source_kind': 'synthetic_diagnostic',
                            'original_source_reviewed': False})
    generated_video = ROOT/'.runtime-work/c179824'/(
        'full-device-'+suffix[-1]+'-primary-compat-v2')/'driver_reference.mkv'
    review = {'source_kind': 'synthetic_diagnostic',
              'trace_sha256': sha(source/'parked-trace.jsonl'),
              'reviewer_id': 'cpu-diagnostic-only',
              'highway_and_shoulder_source_sha256': sha(source/'parked-highway-review.json'),
              'parked_status_source_sha256': sha(source/'parked-status-review.json'),
              'nrs_484d_165_source_sha256': sha(source/'nrs-484d-165-source.json'),
              'pixel_video_name': 'driver_reference.mkv',
              'pixel_video_sha256': sha(generated_video),
              'on_traveled_portion_or_adjacent_shoulder': True,
              'insufficient_light_at_1000ft': True,
              'front_lamp_visible_at_500ft': True,
              'rear_lamp_visible_at_500ft': True,
              'lamp_near_traffic_side': True,
              'headlamp_dimmed_if_lit': True,
              'original_source_reviewed': False}
    write(source/'parked-exception-review.json', review)
    capture = json.loads((source/'capture/manifest.json').read_text())
    capture['case_id'] = case_id
    for name in ('visibility-trace.jsonl', 'vehicle-lamps.jsonl',
                 'parked-trace.jsonl', 'trace.jsonl'):
        capture['sources'][name] = sha(source/name)
    write(source/'capture/manifest.json', capture)
    write(source/'acquisition-provenance.json',
          {'case_id': case_id, 'scope': 'synthetic CPU diagnostic; no original pixels'})
    diagnostic = json.loads((base/'diagnostic.json').read_text())
    for graph in diagnostic['graphs']:
        if graph['attributes']['frame'] >= 1500:
            ego = graph['nodes'][0]['attributes']
            ego['vertex'][1] = -4.75
            for vertex in ego['threedbbox']:
                vertex[1] -= 3.0
    write(target/'diagnostic.json', diagnostic)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': path.relative_to(source).as_posix(),
                           'source': path.relative_to(ROOT).as_posix(),
                           'sha256': sha(path)}
                          for path in sorted(source.rglob('*')) if path.is_file()],
              'generator': {'source': (target/'diagnostic.json').relative_to(ROOT).as_posix(),
                            'sha256': sha(target/'diagnostic.json')}}
    write(target/'recipe.json', recipe)
    return {'case_id': case_id, 'recipe_sha256': sha(target/'recipe.json'),
            'synthetic_only': True}


def main():
    print(json.dumps({'cases': [one(suffix) for suffix in
                                ('parked_lamps_1', 'parked_lamps_2')],
                      'synthetic_only': True}, sort_keys=True))


if __name__ == '__main__':
    main()
