"""Generate explicit synthetic CPU bundles without claiming original provenance."""
import hashlib
import json
from pathlib import Path

from bus_curb import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCES = ('jurisdiction', 'bus_class', 'tour_exclusion', 'operator',
           'location_boundary', 'location_designation', 'signs',
           'curb_geometry', 'right_front_wheel', 'bus_route',
           'loading_activity', 'traffic_route')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned file exceeds 2 MiB')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    note = HERE / 'diagnostic-source-note.json'
    write_json(note, {'format': 'c149470-synthetic-source-note-v1',
                      'source_kind': 'synthetic_diagnostic_fixture',
                      'accepted_original_source': False,
                      'physical_acceptance': False,
                      'cases': [c.name for c in CASES]})
    entries = []
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.name
        scene = {'case_id': case_id, 'source_kind': 'synthetic_diagnostic_fixture',
                 'cell_id': 'C149470', 'actor': 'bus_driver',
                 'operator_controls_bus': True, 'bus_qualifies': True,
                 'tour_bus': False, 'public_street': True,
                 'location_kind': case.location, 'activity': case.activity,
                 'target_distance_m': case.target_distance_m,
                 'location_designated': True, 'location_governs_bus': True,
                 'curb_segment_xy': [[0.0, 0.0], [20.0, 0.0]],
                 'location_boundary_xy': [[0.0, 0.0], [20.0, 0.0]],
                 'bus_route_xy': [[-5.0, 0.5], [5.0, case.target_distance_m]],
                 'traffic_route_xy': [[-5.0, 3.0], [15.0, 3.0]],
                 'loading_actor_ids': ['diagnostic_loading_actor']}
        for source in SOURCES:
            scene[source + '_source_sha256'] = sha(note)
        config = {'law_id': 'LVMC-11-60-030-A4', 'cell_id': 'C149470',
                  'actor': 'bus_driver', 'selected_case_id': case_id,
                  'rate_hz': 20, 'duration_s': 45, 'required_atoms': [],
                  'source_packets': [],
                  'cameras': ['overview', 'approach', 'curb_wheel', 'traffic'],
                  'case': {'kind': case.name, 'case_id': case_id,
                           'location_kind': case.location, 'activity': case.activity}}
        description = {'status': 'diagnostic_only_original_capture_pending',
                       'observations': ['right front wheel and curb',
                                        'stopped passenger or baggage loading',
                                        'bus alignment and other traffic',
                                        'four synchronized cameras']}
        files = {'runner.py': (HERE / 'diagnostic_runner.py').read_text(),
                 'bus_curb.py': (HERE / 'bus_curb.py').read_text(),
                 'tests/test_bundle.py': (HERE / 'diagnostic_bundle_test.py').read_text(),
                 'config.json': json.dumps(config, indent=2) + '\n',
                 'scene.json': json.dumps(scene, indent=2) + '\n'}
        construction = {'law_id': 'LVMC-11-60-030-A4', 'cell_id': 'C149470',
                        'actor': 'bus_driver', 'case_id': case_id,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': description,
                        'files': [{'path': p, 'content': c} for p, c in files.items()]}
        target = HERE / ('construction-diagnostic-' + case.name + '.json')
        write_json(target, construction)
        entries.append({'case_id': case_id, 'kind': 'capability_research',
                        'construction': target.name,
                        'construction_sha256': sha(target),
                        'diagnostic_only': True})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'status': 'diagnostic_only_original_sources_pending',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    write_json(HERE / 'execution-manifest.diagnostic.json', manifest)
    return len(entries)


if __name__ == '__main__':
    print('built diagnostic cases:', build())
