"""Build independent synthetic stop-line source fixtures for CPU checks.

The seed trace is a diagnostic trajectory from the C111325 worker package.
It is copied into this assignment and rebound to its exact case and road.
It is never accepted as an original Native capture or as reused legal proof.
"""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SEED = ROOT / 'work/training__C111325__NRS-484A-450-2__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    results = []
    for condition, label in (('a', 'line_stop'), ('b', 'line_pass')):
        case = PACKAGE.name + '__selected_ef239a06__condition_' + condition
        source = SEED / ('selected-source-' + label)
        target = PACKAGE / ('selected-source-condition-' + condition)
        target.mkdir(exist_ok=True)
        for relative in ('capture/evidence.jsonl', 'capture/native/frames.jsonl',
                         'capture/recorder_info.txt', 'stop_history.jsonl',
                         'trace.jsonl', 'video_frames.jsonl'):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, destination)
        shutil.copyfile(HERE / 'authored-road.xodr', target / 'road.xodr')
        seed_rows = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
        with (target / 'native_samples.jsonl').open('w') as handle:
            for index, row in enumerate(seed_rows):
                vertices = row['body_vertices_m']
                center = (min(v[1] for v in vertices) + max(v[1] for v in vertices)) / 2
                value = {'case_id': case, 'frame': index, 'video_frame': index,
                         'native_frame': row['native_frame'], 'time_s': row['time_s'],
                         'road_id': row['road_id'], 'lane_id': row['lane_id'],
                         'body_vertices_m': vertices, 'speed_mps': row['speed_mps'],
                         'ego': {'center_x_m': center + 11,
                                 'front_x_m': max(v[1] for v in vertices) + 11,
                                 'speed_mps': row['speed_mps']},
                         'source_kind': 'synthetic_cpu_fixture'}
                handle.write(json.dumps(value, allow_nan=False) + '\n')
        reference = {'case_id': case, 'source_kind': 'synthetic_cpu_fixture',
                     'authored_road_sha256': sha(target / 'road.xodr'),
                     'stop_sign_present': True, 'governs_ego_lane': True,
                     'near_crosswalk_present': False, 'marked_stop_line_x_m': 0,
                     'intersection_near_boundary_x_m': 4}
        write(target / 'stop_reference.json', reference)
        seal_names = ('native_samples.jsonl', 'video_frames.jsonl',
                      'stop_reference.json', 'road.xodr')
        seal = {'format': 'c295180-saved-source-seal-v1', 'case_id': case,
                'source_sha256': {name: sha(target / name) for name in seal_names}}
        write(target / 'source-seal.json', seal)
        write(target / 'acquisition-seal.json', seal)
        write(target / 'diagnostic-source-manifest.json',
              {'case_id': case, 'source_kind': 'synthetic_native_sample',
               'sha256': {'road.xodr': sha(target / 'road.xodr'),
                          'native_samples.jsonl': sha(target / 'native_samples.jsonl')}})
        write(target / 'capture/manifest.json',
              {'extraction_confirmed': True, 'frames': 600,
               'synthetic_diagnostic': True,
               'sources': {'road.xodr': sha(target / 'road.xodr'),
                           'trace.jsonl': sha(target / 'trace.jsonl')}})
        write(target / 'crosswalk_geometry.json',
              {'near_side_crosswalk_present': False, 'marked_stop_line_y_m': -11,
               'intersection_entry_y_m': -7,
               'road_sha256': sha(target / 'road.xodr'),
               'source': 'authored OpenDRIVE stop-line object; physical rendering unverified'})
        specification = PACKAGE / ('selected-condition-' + condition + '-fixture-spec.json')
        shutil.copyfile(SEED / ('current-v2-probe-' + ('1' if condition == 'a' else '2') +
                                '-fixture-spec.json'), specification)
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': path.relative_to(target).as_posix(),
                               'source': path.relative_to(ROOT).as_posix(),
                               'sha256': sha(path)}
                              for path in sorted(target.rglob('*')) if path.is_file()],
                  'generator': {'source': specification.relative_to(ROOT).as_posix(),
                                'sha256': sha(specification)}}
        write(PACKAGE / ('selected-condition-' + condition + '-fixture-recipe.json'), recipe)
        results.append({'case_id': case, 'source_seal_sha256': sha(target / 'source-seal.json'),
                        'fixture_recipe_sha256': sha(PACKAGE / ('selected-condition-' + condition + '-fixture-recipe.json'))})
    return results


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
