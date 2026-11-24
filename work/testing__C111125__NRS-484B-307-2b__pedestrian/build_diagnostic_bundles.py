"""Build five exact diagnostic bundles without inventing a reviewed Native site."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
SOURCES = ('runner.py', 'analysis.py', 'native_crossing.py', 'pedestrian_control.py',
           'native_capture.py', 'saved_measurement.py', 'saved_media_audit.py',
           'delivery_audit.py', 'comparison_audit.py')
CAMERAS = [('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
TEST_SOURCE = '''import json
import unittest
from pathlib import Path
from runner import check

class MaterializedBundleTest(unittest.TestCase):
    def test_exact_diagnostic_identity_and_contract(self):
        root = Path(__file__).resolve().parents[1]
        scene = check(root)
        self.assertEqual(json.loads((root / "config.json").read_text())["case"], scene)
        self.assertTrue(scene["diagnostic_only"])
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def diagnostic_sources(suffix):
    crosswalk_kind = 'unmarked' if suffix == 'unmarked_cross' else 'marked'
    outside = suffix == 'outside_cross'
    stop = suffix == 'other_device_stop'
    device = 'DONT_WALK' if suffix.startswith('other_device_') else 'none'
    point_y = 8 if outside else 5
    objects = {
        'map.json': {'public_highway': True,
                     'highway_polygon_xy': [[0, 0], [10, 0], [10, 10], [0, 10]],
                     'crosswalk_polygon_xy': [[0, 4], [10, 4], [10, 6], [0, 6]],
                     'crosswalk_kind': crosswalk_kind, 'crosswalk_qualifies': True},
        'head.json': {'official': True, 'control': 'traffic_light',
                      'head_id': 'diagnostic-head', 'pedestrian_faces_head': True},
        'devices.json': {'other_device_id': 'diagnostic-device', 'inventory_complete': True},
    }
    texts = {name: json.dumps(value, indent=2) + '\n' for name, value in objects.items()}
    refs = [{'path': name, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
            for name, text in texts.items()]
    site = {'cell_id': 'C111125', 'actor': 'pedestrian', 'original_sources': refs,
            'map_source_path': 'map.json', 'signal_source_path': 'head.json',
            'device_inventory_source_path': 'devices.json',
            'official_signal_head_id': 'diagnostic-head', 'pedestrian_faces_head': True,
            'public_highway_source_assertion': True,
            'crosswalk_kind': crosswalk_kind, 'crosswalk_qualification_source_assertion': True,
            'highway_polygon_xy': objects['map.json']['highway_polygon_xy'],
            'crosswalk_polygon_xy': objects['map.json']['crosswalk_polygon_xy'],
            'pedestrian_route_xy': [[-2, point_y], [2, point_y], [11, point_y]],
            'route_crosswalk_expected': not outside, 'other_device_id': 'diagnostic-device',
            'pedestrian_blueprint_id': 'walker.pedestrian.0001',
            'pedestrian_spawn_xyz': [-2, point_y, 0]}
    texts['site.json'] = json.dumps(site, indent=2) + '\n'
    points = [[-2, point_y], [-2, point_y], [-2, point_y]] if stop else [
        [-2, point_y], [2, point_y], [11, point_y]]
    frames = [{'frame': i, 'official_signal_head_id': 'diagnostic-head',
               'pedestrian_faces_head': True, 'lit_aspects': ['circular_green'],
               'pedestrian_xy': point, 'other_device_id': 'diagnostic-device',
               'other_device_indication': device,
               'other_device_mode': 'steady' if device != 'none' else 'absent'}
              for i, point in enumerate(points)]
    texts['frames.json'] = json.dumps(frames, indent=2) + '\n'
    mapping = [{'video_frame': i, 'carla_frame': i, 'time_s': i / 20}
               for i in range(len(frames))]
    trace = [{'frame': i, 'time_s': i / 20,
              'position': {'x': point[0], 'y': point[1], 'z': 0},
              'heading_deg': 0, 'speed_mps': 0 if stop else 1.2}
             for i, point in enumerate(points)]
    texts['video_frames.jsonl'] = ''.join(json.dumps(row) + '\n' for row in mapping)
    texts['trace.jsonl'] = ''.join(json.dumps(row) + '\n' for row in trace)
    videos = [{'path': name + '.mkv', 'frames': len(frames), 'width': width,
               'height': height, 'fps': 20, 'color': 'green'}
              for name, width, height in CAMERAS]
    return {'files': texts, 'graphs': [], 'videos': videos}


def measurement_contract(plan, case, suffix):
    fields = [(0, 'measure_signal', 'c111125_signal', ['site.json', 'head.json', 'frames.json'])]
    if suffix in ('marked_cross', 'unmarked_cross', 'outside_cross'):
        fields.append((1, 'measure_crosswalk', 'c111125_crosswalk',
                       ['site.json', 'map.json', 'frames.json']))
    else:
        fields.append((2, 'measure_device', 'c111125_other_device',
                       ['site.json', 'devices.json', 'frames.json']))
    dispositions = plan['requirement_dispositions']
    rows = [{'disposition_index': index,
             'requirement': dispositions[index]['requirement'],
             'source': dispositions[index]['source'], 'kind': 'measured',
             'method': method, 'output_key': key, 'value_type': 'object', 'inputs': inputs}
            for index, method, key, inputs in fields]
    return {'format': 'worker-measurement-contract', 'case_id': case['case_id'],
            'requirements': rows,
            'negative': {'remove': ['head.json'],
                         'error_contains': 'Missing required source: head.json'},
            'independent_auditor': 'delivery_audit.py',
            'unresolved_judgments': ['Native site identity', 'NRS 484B.283 device applicability',
                                     'physical maneuver and legal permission']}


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    cases = plan['cases']
    if len(cases) != 5 or len({case['case_id'] for case in cases}) != 5:
        raise ValueError('five distinct exact cases required')
    repo = ROOT.parents[1]
    assignment_source = Path('inputs') / ASSIGNMENT / 'assignment.json'
    manifest = {'format': 'worker-diagnostic-case-index', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(repo / 'runtime/SOURCE-MANIFEST.json'),
                'diagnostic_only': True, 'cases': []}
    proposal_cases = []
    for case in cases:
        suffix = case['case_id'].removeprefix(ASSIGNMENT + '__')
        if suffix not in {'marked_cross', 'unmarked_cross', 'other_device_stop',
                          'other_device_cross', 'outside_cross'}:
            raise ValueError('unknown exact pedestrian case')
        scene = {'case_id': case['case_id'], 'case_suffix': suffix,
                 'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                 'actor': plan['actor'], 'diagnostic_only': True,
                 'source_status': 'reviewed Native site missing',
                 'requested_crossing': suffix != 'other_device_stop',
                 'scenario_parameters': case['scenario_parameters']}
        config = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                  'actor': plan['actor'], 'selected_case_id': case['case_id'],
                  'supported_case_ids': [item['case_id'] for item in cases],
                  'case': scene, 'rate_hz': 20, 'duration_s': 45,
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'pose_strategy': 'reviewed original site required'}
                              for name, width, height in CAMERAS]}
        files = [{'path': name, 'content': (ROOT / name).read_text()} for name in SOURCES]
        files += [{'path': 'scene.json', 'content': json.dumps(scene, indent=2) + '\n'},
                  {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                  {'path': 'tests/test_bundle.py', 'content': TEST_SOURCE}]
        construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                        'actor': plan['actor'], 'case_id': case['case_id'],
                        'diagnostic_only': True, 'entrypoint': 'runner.py',
                        'files': files,
                        'mechanisms': ['source-bound Native walker and four-camera capture components; reviewed site absent'],
                        'measurement_plan': ['original frame, signal, device, crosswalk and camera source joins'],
                        'static_checks': ['exact diagnostic identity and capture contract'],
                        'termination_rules': ['no Native dispatch before reviewed site binding']}
        rel = Path('cases') / suffix / 'construction.json'
        write(ROOT / rel, construction)
        contract = Path('cases') / suffix / 'measurement-contract.json'
        write(ROOT / contract, measurement_contract(plan, case, suffix))
        specification = Path('cases') / suffix / 'diagnostic-sources.json'
        write(ROOT / specification, diagnostic_sources(suffix))
        recipe = Path('cases') / suffix / 'diagnostic-recipe.json'
        write(ROOT / recipe, {'format': 'worker-fixture-recipe',
                              'sources': [{'path': 'assignment-source.json',
                                           'source': str(assignment_source),
                                           'sha256': sha(repo / assignment_source)}],
                              'generator': {'source': str(Path('work') / ASSIGNMENT / specification),
                                            'sha256': sha(ROOT / specification)}})
        manifest['cases'].append({'case_id': case['case_id'], 'kind': 'diagnostic',
                                  'construction': str(rel),
                                  'construction_sha256': sha(ROOT / rel),
                                  'measurement_contract': str(contract),
                                  'measurement_procedure': {'entrypoint': 'analysis.py'},
                                  'fixture_recipe': str(Path('work') / ASSIGNMENT / recipe),
                                  'candidate_risk': {'status': 'physical',
                                      'reason': case['physical_risk_assessment']['risk']},
                                  'candidates': []})
        proposal_cases.append({
            'case_id': case['case_id'], 'target_law_id': plan['law_id'],
            'target_type': 'diagnostic_source_join',
            'rationale': case['purpose'],
            'variable_assignments': {
                key: {'kind': 'world_setup' if key in ('crosswalk_kind', 'circular_green_alone',
                                                       'other_device_indication') else 'controller',
                      'value': value}
                for key, value in case['scenario_parameters'].items()},
            'unresolved_judgment_calls': [
                'Native site, official signal and device authority require original source binding',
                'NRS 484B.283 device applicability and legal permission remain unresolved'],
            'diagnostic_only': True})
    write(ROOT / 'diagnostic-manifest.json', manifest)
    write(ROOT / 'proposals/cases.json', {
        'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
        'diagnostic_only': True, 'cases': proposal_cases})
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases']), 'diagnostic_only': True}))
