"""Build seven source-specific synthetic recipes for pinned CPU compatibility."""
import copy
import hashlib
import json
from pathlib import Path

from bus_curb import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
DONOR = ROOT / 'work/testing__C135087__NRS-484B-517__motor_vehicle_driver'
DONOR_SOURCE = DONOR / 'diagnostics/loading_open_waiting'
DONOR_GENERATOR = DONOR / 'diagnostics/loading_open_waiting-generator.json'
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
DESC = {'channels': [
    {'name': 'right_front_wheel_curb', 'unit': 'm with uncertainty',
     'method': 'right-front-wheel XY point to reviewed curb segment, 20 Hz',
     'sampling_rate_hz': 20, 'time_window': 'stopped loading frames',
     'reference_frame': 'original frame/time', 'uncertainty': 'wheel localization'},
    {'name': 'stopped_loading', 'unit': 'structured original observation',
     'method': 'bus speed and actual loading actor state, 20 Hz',
     'sampling_rate_hz': 20, 'time_window': 'all 900 frames',
     'reference_frame': 'original frame/time', 'uncertainty': 'actor activity review'},
    {'name': 'other_traffic', 'unit': 'm/s',
     'method': 'separate vehicular traffic speed, 20 Hz',
     'sampling_rate_hz': 20, 'time_window': 'all 900 frames',
     'reference_frame': 'original frame/time', 'uncertainty': 'traffic route review'},
    {'name': 'camera_frame_identity', 'unit': 'frame ID',
     'method': 'four synchronized cameras, 20 Hz',
     'sampling_rate_hz': 20, 'time_window': 'all 900 frames',
     'reference_frame': 'original frame/time', 'uncertainty': 'pixel visibility review'}],
    'context_inputs': [],
    'limitations': ['Approximately parallel and unduly impede remain unresolved judgments.',
                    'Synthetic fixture is software diagnostic only.']}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned file exceeds 2 MiB: ' + str(path))


def build():
    donor = json.loads(DONOR_GENERATOR.read_text())
    note = HERE / 'diagnostic-source-note.json'
    source_names = ('trace.jsonl', 'video_frames.jsonl',
                    'capture/native/frames.jsonl', 'capture/evidence.jsonl')
    entries = []
    proposals = []
    for case in CASES:
        cid = AID + '__' + case.name
        folder = HERE / 'diagnostics' / case.name
        folder.mkdir(parents=True, exist_ok=True)
        original = json.loads((HERE / ('construction-diagnostic-' + case.name + '.json')).read_text())
        files = {item['path']: item['content'] for item in original['files']}
        config = json.loads(files['config.json'])
        config['case']['recording_description'] = DESC
        config['cameras'] = list(NAMES)
        files['config.json'] = json.dumps(config, indent=2) + '\n'
        files['analysis.py'] = (HERE / 'analysis.py').read_text()
        original['recording_description'] = DESC
        original['files'] = [{'path': path, 'content': text}
                             for path, text in files.items()]
        construction = HERE / ('construction-compatibility-' + case.name + '.json')
        dump(construction, original)
        proposals.append({'case_id': cid, 'target_law_id': 'LVMC-11-60-030-A4',
                          'target_type': 'boundary_probe', 'status': 'draft',
                          'rationale': 'Exact synthetic CPU probe; original site and legal judgment pending.',
                          'variable_assignments': {'location_kind': case.location,
                                                   'activity': case.activity,
                                                   'target_distance_m': case.target_distance_m},
                          'unresolved_judgment_calls': ['approximately parallel',
                                                        'unduly impede'],
                          'recording_description': DESC})
        scene = json.loads(files['scene.json'])
        donor_rows = json.loads((DONOR_SOURCE / 'actor-rows.json').read_text())
        rows = []
        for index, old in enumerate(donor_rows):
            row = {'original_frame': old['frame'], 'time_s': old['time_s'],
                   'bus_id': 'synthetic-bus', 'traffic_id': 'synthetic-traffic',
                   'activity': case.activity,
                   'bus_speed_mps': 2 if index < 100 else 0,
                   'traffic_speed_mps': 3, 'loading_active': index >= 150,
                   'right_front_wheel_xy': [5, case.target_distance_m],
                   'wheel_position_uncertainty_m': .001, 'bus_curb_angle_deg': 2}
            for name in ('frame', 'bus_motion', 'traffic_motion', 'right_front_wheel',
                         'curb_geometry', 'location_designation', 'loading_activity'):
                row[name + '_source_sha256'] = scene.get(name + '_source_sha256',
                                                           scene['bus_route_source_sha256'])
            rows.append(row)
        dump(folder / 'bus-rows.json', rows, compact=True)
        copied = []
        for name in source_names:
            source = DONOR_SOURCE / name
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            copied.append({'path': name, 'source': str(target.relative_to(ROOT)),
                           'sha256': sha(target)})
        provenance = folder / 'acquisition-provenance.json'
        dump(provenance, {'provenance_kind': 'synthetic_fixture',
                          'diagnostic_fixture': True,
                          'scope': 'source-shaped CPU software diagnostic only'})
        copied += [{'path': 'bus-rows.json',
                    'source': str((folder / 'bus-rows.json').relative_to(ROOT)),
                    'sha256': sha(folder / 'bus-rows.json')},
                   {'path': 'diagnostic-source-note.json',
                    'source': str(note.relative_to(ROOT)), 'sha256': sha(note)},
                   {'path': 'acquisition-provenance.json',
                    'source': str(provenance.relative_to(ROOT)),
                    'sha256': sha(provenance)}]
        generator = copy.deepcopy(donor)
        generator['files']['capture/manifest.json'] = json.dumps({
            'acquisition': 'synthetic_fixture', 'case_id': cid,
            'extraction_confirmed': True, 'frames': 900,
            'observation_contract_version': 2, 'required_observations': [],
            'complete_driving_lanes': True,
            'native_map_facts': {'path': 'native_map_facts.json',
                                 'sha256': hashlib.sha256(generator['files']['capture/native_map_facts.json'].encode()).hexdigest()},
            'sources': {'road.xodr': hashlib.sha256(generator['files']['road.xodr'].encode()).hexdigest(),
                        'trace.jsonl': sha(folder / 'trace.jsonl')}}, indent=2) + '\n'
        generator_path = HERE / 'diagnostics' / (case.name + '-generator.json')
        dump(generator_path, generator, compact=True)
        recipe = {'format': 'worker-fixture-recipe', 'sources': copied,
                  'generator': {'source': str(generator_path.relative_to(ROOT)),
                                'sha256': sha(generator_path)}}
        recipe_path = HERE / 'diagnostics' / (case.name + '-recipe.json')
        dump(recipe_path, recipe)
        contract = {'format': 'worker-measurement-contract', 'case_id': cid,
                    'requirements': [{'disposition_index': 0,
                                      'requirement': 'Right-front-wheel distance during stopped loading at qualifying public-street location',
                                      'source': 'inputs/testing__C149470__LVMC-11-60-030-A4__bus_driver/assignment.json',
                                      'output_key': 'wheel_curb_interval',
                                      'method': 'measure_wheel_curb', 'value_type': 'object',
                                      'kind': 'measured',
                                      'inputs': ['bus-rows.json', 'diagnostic-source-note.json']}],
                    'negative': {'remove': ['bus-rows.json'],
                                 'error_contains': 'Missing required source: bus-rows.json'}}
        contract_path = HERE / 'diagnostics' / (case.name + '-measurement-contract.json')
        dump(contract_path, contract)
        entries.append({'case_id': cid, 'kind': 'capability_research',
                        'construction': construction.name,
                        'construction_sha256': sha(construction),
                        'fixture_recipe': str(recipe_path.relative_to(ROOT)),
                        'measurement_contract': str(contract_path.relative_to(HERE)),
                        'measurement_procedure': {'entrypoint': 'analysis.py'}})
    proposal = {'cell_id': 'C149470', 'actor': 'bus_driver', 'status': 'draft',
                'sweep_specs': [], 'cases': proposals}
    dump(HERE / 'proposals/cases.json', proposal)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'status': 'synthetic_compatibility_only',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    dump(HERE / 'execution-manifest.compatibility-diagnostic.json', manifest)
    return len(entries)


if __name__ == '__main__':
    print('compatibility recipes:', build())
