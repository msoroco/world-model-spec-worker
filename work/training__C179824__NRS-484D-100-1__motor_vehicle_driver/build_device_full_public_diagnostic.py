"""Build synthetic transport fixtures for full-law device replacement drafts."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
BASE = HERE/'cases/minutes_after_sunset_at'
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


def line(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n'


def one(suffix):
    case = ASSIGNMENT+'__'+suffix
    target = HERE/'cases'/('full_'+suffix)
    source = target/'source'
    source.mkdir(parents=True, exist_ok=True)
    base_source = BASE/'source'
    for path in base_source.rglob('*'):
        if path.is_file():
            output = source/path.relative_to(base_source)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output)
    trace = [json.loads(line) for line in
             (source/'visibility-trace.jsonl').read_text().splitlines() if line]
    lamp_on = suffix == 'controlled_1'
    with (source/'vehicle-lamps.jsonl').open('w') as stream:
        for item in trace:
            index = item['video_frame']
            stream.write(line({
                'video_frame': index, 'native_frame': item['native_frame'],
                'time_s': item['time_s'], 'vehicle_id': '107',
                'vehicle_blueprint_id': 'vehicle.tesla.model3',
                'road_id': '1', 'vehicle_xy_m': item['ego_xy_m'],
                'speed_mps': item['ego_speed_mps'],
                'device_active': index >= 100,
                'headlamp_setting_on': lamp_on,
                'position_lamp_setting_on': lamp_on,
                'native_light_state_bits': 3 if lamp_on else 0,
                'camera_native_frames': item['camera_native_frames']}))
    context = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_diagnostic',
               'road_id': '1', 'map_source_sha256': sha(source/'road.xodr'),
               'state': 'Nevada', 'public_highway': None, 'vehicle_class': None,
               'directive': 'use_lamps', 'device_official': None,
               'device_governs_road_id': '1'}
    (source/'lamp-context.json').write_text(line(context))
    review = {'case_id': case, 'review_kind': 'synthetic_diagnostic',
              'original_context_sha256': sha(source/'lamp-context.json'),
              'state': 'Nevada', 'public_highway': True,
              'vehicle_class': 'ordinary_motor_vehicle',
              'directive': 'use_lamps', 'device_official': True,
              'device_governs_road_id': '1'}
    for field, name in REVIEW_SOURCES.items():
        (source/name).write_text(line({
            'case_id': case, 'review_kind': 'synthetic_diagnostic',
            'source_note': 'CPU source-shape fixture'}))
        review[field] = sha(source/name)
    (source/'lamp-source-review.json').write_text(line(review))
    capture_manifest = json.loads((source/'capture/manifest.json').read_text())
    capture_manifest['case_id'] = case
    capture_manifest['sources']['vehicle-lamps.jsonl'] = sha(source/'vehicle-lamps.jsonl')
    write(source/'capture/manifest.json', capture_manifest)
    write(source/'acquisition-provenance.json',
          {'case_id': case, 'scope': 'synthetic CPU diagnostic; no original pixels'})
    shutil.copyfile(BASE/'diagnostic.json', target/'diagnostic.json')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': path.relative_to(source).as_posix(),
                           'source': path.relative_to(ROOT).as_posix(),
                           'sha256': sha(path)}
                          for path in sorted(source.rglob('*')) if path.is_file()],
              'generator': {'source': (target/'diagnostic.json').relative_to(ROOT).as_posix(),
                            'sha256': sha(target/'diagnostic.json')}}
    write(target/'recipe.json', recipe)
    return {'case_id': case, 'recipe_sha256': sha(target/'recipe.json'),
            'source_files': len(recipe['sources']), 'synthetic_only': True}


def main():
    print(json.dumps({'cases': [one(suffix) for suffix in
                                ('controlled_1', 'controlled_2')],
                      'synthetic_only': True}, sort_keys=True))


if __name__ == '__main__':
    main()
