"""Build exact, source-hashed textual scooter diagnostics; no physical evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SPEEDS = {'controlled_1': 12, 'controlled_at_cap': 15, 'controlled_2': 17}
SOURCES = ('scooter_classification_source', 'scooter_mass_source',
           'scooter_motor_max_speed_source', 'path_surface_source',
           'path_continuity_source', 'path_access_source',
           'roadway_boundary_source', 'ordinance_applicability_source',
           'ordinance_review_source', 'scooter_handlebars_source',
           'scooter_electric_motor_source', 'scooter_riding_design_source',
           'scooter_propulsion_source', 'contrary_posting_source',
           'local_definition_applicability_source', 'assistive_device_intent_source')


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def main():
    for suffix, mph in SPEEDS.items():
        root = HERE / ('cases/' + suffix)
        root.mkdir(parents=True, exist_ok=True)
        frames = ''.join(json.dumps({'video_frame': i, 'native_frame': 100+i,
                                     'time_s': round(i*.05, 8)})+'\n' for i in range(600))
        trace = ''.join(json.dumps({'video_frame': i, 'native_frame': 100+i,
                                    'source_kind': 'synthetic_native_sample',
                                    'device_actor_id': 1, 'rider_actor_id': 2,
                                    'device_center_xy_m': [round(i*.1, 8), 0],
                                    'device_speed_mps': mph*.44704})+'\n' for i in range(600))
        context = {'assignment_id': AID, 'case_id': AID + '__' + suffix,
                   'requested_speed_mps': mph*.44704,
                   'review_kind': 'synthetic_diagnostic',
                   'device_subtype': 'electric_scooter', 'device_actor_id': 1,
                   'rider_actor_id': 2, 'path_box_xyxy_m': [-1, -2, 61, 2],
                   'scooter_rider_excluded_mass_lb': 45,
                   'scooter_motor_only_max_mph': 18,
                   'ordinance_exception_reviewed': True,
                   'path_access_reviewed': True}
        context.update({key: 'synthetic-fixture:' + key for key in SOURCES})
        spec = {'files': {'video_frames.jsonl': frames,
                          'native_rider_trace.jsonl': trace,
                          'scooter_context.json': json.dumps(context)+'\n'},
                'graphs': [],
                'videos': [{'path': 'camera_' + name + '.mkv',
                            'frames': 600, 'width': 16, 'height': 16,
                            'fps': 20, 'color': 'black'}
                           for name in ('forward', 'rear', 'left', 'right')]}
        spec_path = root/'diagnostic.json'
        write(spec_path, spec)
        rel = str(spec_path.relative_to(HERE.parents[1]))
        digest = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': rel,
                               'sha256': digest}],
                  'generator': {'source': rel, 'sha256': digest}}
        write(root/'recipe.json', recipe)
        print(json.dumps({'case': suffix, 'recipe': str(root/'recipe.json'),
                          'source_sha256': digest}, sort_keys=True))


if __name__ == '__main__':
    main()
