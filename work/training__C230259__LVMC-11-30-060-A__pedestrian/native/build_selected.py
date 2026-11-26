"""Promote the two source-metered drafts into exact Native delivery bundles."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
TERMS = ('ru.subject', 'st.crosswalk', 'st.intersection', 'st.roadway',
         'rel.occupies', 'drv.approaching', 'drv.yields_to',
         'drv.hard_deceleration', 'drv.arrival_order')
CAMERAS = (
    ('overview', 1920, 1080, 'fixed world overview of entire crossing'),
    ('approach', 1280, 720, 'fixed world view of pedestrian entry'),
    ('reference_corner', 1280, 720, 'fixed world view of vehicle approach'),
    ('driver_reference', 1280, 720, 'fixed world view of roadway crossing'),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    entries = []
    for suffix, departure in (('probe_01', 320), ('probe_02', 140)):
        case = AID + '__' + suffix
        folder = ROOT / 'cases' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        for source, target in (('selected_runner.py', 'runner.py'),
                               ('selected_finalize.py', 'finalize.py'),
                               ('crossing_meter.py', 'crossing_meter.py'),
                               ('draft_road.xodr', 'road.xodr')):
            (folder / target).write_bytes((ROOT / 'native' / source).read_bytes())
        description = {'channels': [
            {'name': term, 'unit': 'source observation',
             'method': 'original post-tick pedestrian/vehicle history and surveyed roadway geometry',
             'reference_frame': 'original Native C230259 pedestrian and roadway vehicle frames',
             'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
             'uncertainty': 'Actual physical movement, pixels and designated-place applicability need local review'}
            for term in TERMS],
            'context_inputs': [],
            'limitations': ['CPU diagnostic does not establish original physical right-of-way',
                            'Section 11.30.070 applicability requires source review']}
        config = {'assignment_id': AID, 'case_id': case, 'selected_case_id': case,
                  'supported_case_ids': [AID + '__probe_01', AID + '__probe_02'],
                  'law_id': 'LVMC-11-30-060-A', 'cell_id': 'C230259', 'actor': 'pedestrian',
                  'rate_hz': 20, 'duration_s': 30, 'frames': 600,
                  'pedestrian_departure_frame': departure,
                  'candidate_id': 'primary', 'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'fov_deg': 85, 'pose_strategy': pose}
                              for name, width, height, pose in CAMERAS],
                  'case': {'case_id': case}, 'physical_completion': {},
                  'physical_acceptance_claimed': False,
                  'recording_description': description}
        write(folder / 'config.json', config)
        test = '''import json\nimport unittest\nfrom pathlib import Path\nimport runner\n\nclass SelectedCrossing(unittest.TestCase):\n def test_exact_native_request(self):\n  config=json.loads(Path('config.json').read_text())\n  self.assertTrue(runner.check(config)['passed'])\n  self.assertEqual(runner.request(config['pedestrian_departure_frame']-1, config['case_id'])['pedestrian_target_speed_mps'],0)\n  self.assertGreater(runner.request(config['pedestrian_departure_frame'], config['case_id'])['pedestrian_target_speed_mps'],0)\n def test_wrong_case_rejected(self):\n  config=json.loads(Path('config.json').read_text())\n  config['case_id']='wrong'\n  with self.assertRaises(ValueError):runner.check(config)\n'''
        (folder / 'tests').mkdir(exist_ok=True)
        (folder / 'tests/test_selected.py').write_text(test)
        files = [{'path': str(p.relative_to(folder)), 'content': p.read_text()}
                 for p in (folder / 'runner.py', folder / 'finalize.py',
                           folder / 'crossing_meter.py', folder / 'road.xodr',
                           folder / 'config.json', folder / 'tests/test_selected.py')]
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case, 'cell_id': 'C230259', 'law_id': 'LVMC-11-30-060-A',
                        'actor': 'pedestrian', 'entrypoint': 'runner.py', 'files': files,
                        'recording_description': description,
                        'measurement_plan': {'method': 'original source-joined body occupancy, all roadway vehicles and crosswalk survey',
                                             'depart_frame': departure, 'legal_judgment_automated': False},
                        'static_checks': ['surveyed no intersection or marked crosswalk',
                                          '600 original 20 Hz Native frames', 'four synchronized source cameras'],
                        'termination_rules': ['600 original frames', 'abort on missing camera/frame or changed map'],
                        'mechanisms': ['walker applies Native crossing control',
                                       'roadway vehicle velocity retained', 'source-bound crossing meter']}
        construction_path = ROOT / f'selected-{suffix}-construction.json'
        write(construction_path, construction)
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'requirements': [{'disposition_index': 0, 'requirement': 'LVMC-11-30-060-A',
                                      'source': 'inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json',
                                      'output_key': 'crossing_measurement', 'method': 'crossing_measurement',
                                      'kind': 'measured', 'value_type': 'object',
                                      'inputs': ['post-tick.jsonl', 'crossing-context.json']}],
                    'negative': {'remove': ['post-tick.jsonl'],
                                 'error_contains': 'Missing required source: post-tick.jsonl'}}
        contract_path = ROOT / f'selected-{suffix}-measurement-contract.json'
        write(contract_path, contract)
        entries.append({'case_id': case, 'kind': 'delivery',
                        'construction': construction_path.name,
                        'construction_sha256': sha(construction_path),
                        'measurement_contract': contract_path.name,
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Original walker spawn or roadway vehicle timing may fail; use source-measured failure before changing spawn or timing.'},
                        'candidates': []})
    write(ROOT / 'selected-draft-manifest.json', {'format': 'worker-execution-manifest',
          'assignment_id': AID,
          'runtime_manifest_sha256': sha(Path('runtime/SOURCE-MANIFEST.json')),
          'status': 'selected_cpu_proofs_pending', 'original_native_observed': False,
          'delivery_ready': False, 'cases': entries})


if __name__ == '__main__':
    main()
