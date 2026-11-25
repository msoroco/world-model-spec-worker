"""Create explicit synthetic source fixtures for saved rider-count CPU checks."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
AID = FOLDER.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n')


def jsonlines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def main():
    for label, count in (('controlled_1', 2), ('controlled_2', 3)):
        for candidate, shift in (('primary', 0.0), ('fallback1', .18)):
            prefix = f'diagnostic-{label}-{candidate}'
            ids = list(range(1, count + 1))
            context = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic',
                       'reviewer': 'synthetic fixture', 'rider_ids': ids,
                       'device_subtypes': {str(i): 'bicycle' for i in ids},
                       'exclusive_use_reviewed': True, 'legal_verdict': None}
            for key in ('public_dedication_source', 'public_vehicle_access_source',
                        'roadway_boundary_source', 'shoulder_boundary_source',
                        'exclusive_use_source', 'exclusive_use_review_source',
                        'rider_device_source', 'bicycle_wheel_source',
                        'bicycle_diameter_source', 'bicycle_moped_exclusion_source'):
                context[key] = 'synthetic-fixture:' + key
            pose_rows = []
            frame_rows = []
            trace_rows = []
            evidence_rows = []
            for i in range(600):
                native = 1000 + i
                t = round(i * .05, 5)
                frame_rows.append({'video_frame': i, 'native_frame': native,
                                   'time_s': t,
                                   'camera_native_frames': {view: native for view in VIEWS}})
                pose_rows.append({'video_frame': i, 'native_frame': native,
                                  'source_kind': 'synthetic_native_sample',
                                  'riders': [{'rider_id': rid,
                                              'longitudinal_m': round(i * .1, 5),
                                              'lateral_m': round(rid * 1.5 + shift, 5),
                                              'half_length_m': .8, 'speed_mps': 2,
                                              'roadway_occupied': True,
                                              'shoulder_occupied': False,
                                              'exclusive_use_occupied': False}
                                             for rid in ids]})
                trace_rows.append({'frame': native, 'time_s': t,
                                   'position_m': round(i * .1, 5)})
                evidence_rows.append({'original_frame': native,
                                      'source_kind': 'synthetic_fixture'})
            sources = []
            for name, data in (('road_context.json', json.dumps(context, separators=(',', ':')) + '\n'),
                               ('rider_poses.jsonl', jsonlines(pose_rows)),
                               ('video_frames.jsonl', jsonlines(frame_rows))):
                source = FOLDER / f'{prefix}-{name}'
                source.write_text(data)
                sources.append({'path': name, 'source': f'work/{AID}/{source.name}',
                                'sha256': sha(source)})
            spec = {'files': {'trace.jsonl': jsonlines(trace_rows),
                              'capture/evidence.jsonl': jsonlines(evidence_rows)},
                    'graphs': [],
                    'videos': [{'path': name + '.mkv', 'frames': 600,
                                'width': 1920 if name == 'overview' else 1280,
                                'height': 1080 if name == 'overview' else 720,
                                'fps': 20, 'color': 'black'} for name in VIEWS]}
            spec_path = FOLDER / (prefix + '.json')
            write(spec_path, spec)
            recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
                      'generator': {'source': f'work/{AID}/{spec_path.name}',
                                    'sha256': sha(spec_path)}}
            recipe_path = FOLDER / (prefix + '-recipe.json')
            write(recipe_path, recipe)
            print(json.dumps({'case': label, 'candidate': candidate,
                              'recipe_sha256': sha(recipe_path)}))


if __name__ == '__main__':
    main()
