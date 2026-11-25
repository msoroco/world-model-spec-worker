"""Generate the six exact primary/fallback source-gated offline bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from speed_zone import CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ID = ROOT.name


def content(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    names = [ID + '__' + case.case_id for case in CASES]
    cameras = []
    for name, width, height in (('overview', 1920, 1080), ('approach', 1280, 720),
                                ('reference_corner', 1280, 720),
                                ('driver_reference', 1280, 720)):
        cameras.append({'name': name, 'width': width, 'height': height, 'fov_deg': 75,
                        'pose_strategy': 'reviewed zone boundary, directional sign and full ego passage'})
    channels = []
    for observation in plan['observations']:
        channels.append({'name': observation['name'], 'unit': observation['unit'],
                         'method': observation['source'], 'sampling_rate_hz': 20,
                         'time_window': 'full original 45-second episode',
                         'reference_frame': 'source-sealed original Native frame map',
                         'uncertainty': 'physical realization and legal judgment unresolved'})
    recording = {'channels': channels,
                 'context_inputs': [{'name': 'reviewed_speed_site_packet',
                                     'unit': 'source record',
                                     'method': 'source-hashed zone order, signs, route lanes and vehicle class'}],
                 'limitations': ['No reviewed original C136559 speed-zone site is in frozen input.',
                                 'Requested speed is distinct from original measured speed.']}
    shared = ['runner.py', 'analysis.py', 'speed_zone.py', 'speed_site.py', 'native_capture.py',
              'saved_audit.py', 'case-plan.json', 'tests/test_speed_zone.py',
              'tests/test_speed_site.py', 'tests/test_saved_audit.py']
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ID,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'diagnostic_only': True, 'cases': []}
    for case in CASES:
        exact = ID + '__' + case.case_id
        base_config = {'assignment_id': ID, 'selected_case_id': exact,
                       'law_id': 'NRS-484B-620-2', 'cell_id': 'C136559',
                       'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                       'frame_count': 900, 'duration_s': 45, 'cameras': cameras,
                       'supported_case_ids': names, 'required_atoms': [],
                       'source_packets': [], 'case': {'case_id': exact,
                       'draft_variables': {'direction': case.direction,
                                           'requested_mph': case.requested_mph,
                                           'zone_mode': case.zone_mode}},
                       'control': {'throttle_gain': 0.4, 'brake_gain': 0.3,
                                   'source': 'engineering controller tuning, not a legal threshold'}}
        selected = plan['cases'][[item['case_id'] for item in plan['cases']].index(exact)]
        entry = {'case_id': exact, 'kind': 'delivery', 'diagnostic_only': True,
                 'candidate_risk': {'status': 'physical', 'reason': selected['physical_risk']['reason']},
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                 'candidates': [],
                 'measurement_procedure': {'entrypoint': 'analysis.py'},
                 'fixture_recipe': 'work/' + ID + '/diagnostic-' + case.case_id + '-recipe.json',
                 'acquisition': {name: {'entrypoint': 'analysis.py',
                                        'method': 'source-sealed original capture and saved finalizer',
                                        'evidence': 'original-attempt/capture.json'}
                                 for name in (item['name'] for item in plan['observations'])}}
        measurement = {'format': 'worker-measurement-contract', 'case_id': exact,
                       'requirements': [{'disposition_index': 0,
                           'requirement': plan['requirement_dispositions'][0]['requirement'],
                           'source': plan['requirement_dispositions'][0]['source'],
                           'output_key': 'speed_zone_history', 'method': 'build',
                           'value_type': 'object', 'kind': 'measured',
                           'inputs': ['original-attempt/capture.json',
                                      'original-attempt/capture-source-seal.json',
                                      'original-attempt/site-packet.json']}],
                       'negative': {'remove': ['original-attempt/capture.json'],
                                    'error_contains': 'Missing required source: original-attempt/capture.json'}}
        measure_path = ROOT / 'cases' / case.case_id / 'measurement-contract.json'
        measure_path.parent.mkdir(parents=True, exist_ok=True)
        measure_path.write_text(content(measurement))
        entry['measurement_contract'] = str(measure_path.relative_to(ROOT))
        for candidate in ('primary', 'fallback1'):
            config = json.loads(json.dumps(base_config))
            if candidate == 'fallback1':
                config['control']['throttle_gain'] = 0.5
            files = [{'path': 'config.json', 'content': content(config)}]
            for name in shared:
                files.append({'path': name, 'content': (ROOT / name).read_text()})
            construction = {'case_id': exact, 'law_id': 'NRS-484B-620-2',
                            'cell_id': 'C136559', 'actor': 'motor_vehicle_driver',
                            'candidate_id': candidate, 'entrypoint': 'runner.py',
                            'files': files, 'recording_description': recording,
                            'measurement_plan': {'case_id': exact, 'original_frames': 900,
                                                 'measurements': [x['name'] for x in plan['observations']],
                                                 'legal_judgment': 'unresolved'},
                            'mechanisms': ['reviewed original zone and sign site',
                                           'source-sealed four-camera Native capture'],
                            'static_checks': ['exact identity', 'source hashes', 'directional lanes'],
                            'termination_rules': ['900 original frames',
                                                  'fail closed on absent reviewed site']}
            path = ROOT / 'cases' / case.case_id / candidate / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content(construction))
            if candidate == 'primary':
                entry.update(construction=str(path.relative_to(ROOT)), construction_sha256=sha(path))
                if case == CASES[0]:
                    (ROOT / 'config.json').write_text(content(config))
                    (ROOT / 'construction.json').write_text(content(construction))
            else:
                entry['candidates'].append({'id': 'fallback1',
                    'construction': str(path.relative_to(ROOT)),
                    'construction_sha256': sha(path),
                    'trigger': {'source': 'original Native speed history',
                                'metric': 'actual speed within established zone',
                                'failure_condition': 'requested speed not sustained in original full-zone window'},
                    'changed_knobs': ['throttle_gain 0.4 to 0.5']})
        manifest['cases'].append(entry)
    (ROOT / 'execution-manifest.json').write_text(content(manifest))
    print('built six exact primary/fallback source-gated bundles')


if __name__ == '__main__':
    main()
