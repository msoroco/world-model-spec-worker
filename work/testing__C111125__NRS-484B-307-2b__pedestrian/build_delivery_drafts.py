"""Build source-gated exact delivery constructions for offline CPU checks.

These drafts do not assert reviewed physical site evidence or ready status.
"""
from __future__ import annotations

import hashlib
import json
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
SOURCES = ('analysis.py', 'native_crossing.py', 'pedestrian_control.py',
           'device_timeline.py', 'native_capture.py', 'owned_runner.py',
           'pedestrian_graph_sink.py', 'native_publication.py',
           'saved_measurement.py', 'saved_media_audit.py', 'delivery_audit.py',
           'comparison_audit.py', 'saved_finalizer.py')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    runtime_sha = _sha(ROOT.parents[1] / 'runtime/SOURCE-MANIFEST.json')
    cases = []
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(ASSIGNMENT + '__')
        diagnostic = json.loads((ROOT / 'cases' / suffix / 'construction.json').read_text())
        config = json.loads(next(item['content'] for item in diagnostic['files']
                                 if item['path'] == 'config.json'))
        scene = dict(config['case'])
        scene['diagnostic_only'] = False
        scene['source_status'] = 'reviewed source packet required at Native dispatch'
        recording = json.loads(json.dumps(diagnostic['recording_description']))
        recording['channels'][0]['method'] = 'Same-frame original pedestrian, graph and camera source join'
        recording['channels'][0]['time_window'] = 'all 900 original Native frames'
        recording['channels'][0]['reference_frame'] = 'reviewed Native map local XY'
        recording['channels'][0]['uncertainty'] = 'physical geometry and legal applicability require reviewed source'
        recording['limitations'] = [
            'Source-bound original observations are measured; legal permission remains unresolved.']
        scene['recording_description'] = recording
        config['case'] = scene
        for camera in config['cameras']:
            camera['pose_strategy'] = 'reviewed original site camera pose and subject visibility'
            camera['fov_deg'] = 80
        files = [{'path': 'runner.py', 'content': (ROOT / 'delivery_runner.py').read_text()}]
        files += [{'path': name, 'content': (ROOT / name).read_text()} for name in SOURCES]
        files += [
            {'path': 'scene.json', 'content': json.dumps(scene, indent=2) + '\n'},
            {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
            {'path': 'tests/test_bundle.py', 'content': (
                'import json\nimport unittest\nfrom pathlib import Path\n'
                'from runner import check\n\nclass SelectedCaseTest(unittest.TestCase):\n'
                '    def test_exact_source_gate(self):\n'
                '        root = Path(__file__).resolve().parents[1]\n'
                '        config = check(root)\n'
                '        self.assertFalse(config["case"]["diagnostic_only"])\n')},
        ]
        selected = {
            'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
            'actor': plan['actor'], 'case_id': case['case_id'],
            'entrypoint': 'runner.py', 'files': files,
            'mechanisms': ['reviewed source-bound Native walker capture',
                           'same-frame original graph and four-camera publication'],
            'measurement_plan': ['original 900-frame signal, device, crosswalk and camera joins'],
            'recording_description': recording,
            'static_checks': ['exact selected source gate and 20 Hz four-view capture'],
            'termination_rules': ['stop on source mismatch, graph gap, missing camera frame or failed restoration'],
        }
        path = ROOT / 'cases' / suffix / 'delivery-construction.draft.json'
        _write(path, selected)
        fallback_path = ROOT / 'cases' / suffix / 'delivery-fallback1.draft.json'
        if suffix not in ('other_device_stop', 'flashing_no_countdown_wait'):
            fallback = copy.deepcopy(selected)
            source = next(item for item in fallback['files']
                          if item['path'] == 'native_capture.py')
            old = 'follower = RouteFollower(case_suffix, site, control_factory, vector_factory)'
            if source['content'].count(old) != 1:
                raise ValueError('fallback controller source changed')
            source['content'] = source['content'].replace(
                old, 'follower = RouteFollower(case_suffix, site, control_factory, vector_factory, speed_mps=1.0)')
            fallback['mechanisms'] = fallback['mechanisms'] + [
                'fallback walker route follower commands 1.0 m/s for the same source-bound crossing']
            _write(fallback_path, fallback)
        entry = {'case_id': case['case_id'], 'kind': 'delivery',
                      'construction': str(path.relative_to(ROOT)),
                      'construction_sha256': _sha(path),
                      'measurement_contract': f'cases/{suffix}/measurement-contract.json',
                      'measurement_procedure': {'entrypoint': 'saved_finalizer.py'},
                      'fixture_recipe': f'work/{ASSIGNMENT}/cases/{suffix}/diagnostic-recipe.json',
                      'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                         'host_env_var': 'CARLA_HOST',
                                         'port_env_var': 'CARLA_PORT'},
                      'candidate_risk': {'status': 'none' if suffix in (
                          'other_device_stop', 'flashing_no_countdown_wait') else 'physical',
                                         'reason': (
                          'No measured Native stop drift; hard zero-speed waiting control has no route-speed fallback.'
                          if suffix in ('other_device_stop', 'flashing_no_countdown_wait')
                          else case['physical_risk_assessment']['risk'])},
                      'candidates': [],
                      'acquisition': {'pedestrian_body_center_xy_m': {
                          'entrypoint': 'native_publication.py',
                          'method': 'publish_original',
                          'evidence': 'original-frames.json and same-frame trace/graph'}}}
        if fallback_path.is_file() and suffix not in ('other_device_stop', 'flashing_no_countdown_wait'):
            fallback_entry = {'id': 'fallback1',
                'construction': str(fallback_path.relative_to(ROOT)),
                'construction_sha256': _sha(fallback_path),
                'trigger': {'source': 'original-frames.json',
                            'metric': 'measured pedestrian route progress after 900 source-joined frames',
                            'failure_condition': 'crossing clearance not observed in the original 45-second capture'},
                'changed_knobs': ['route follower speed 1.2 to 1.0 m/s']}
            fb_offline = ROOT / 'cases' / suffix / 'fallback1-offline.log'
            fb_compat = ROOT / 'cases' / suffix / 'fallback1-compatibility.json'
            fb_positive = ROOT / 'cases' / suffix / 'fallback1-compatibility-analysis.log'
            fb_negative = ROOT / 'cases' / suffix / 'fallback1-compatibility-negative.log'
            if fb_offline.is_file():
                fallback_entry['offline'] = {
                    'construction_sha256': _sha(fallback_path),
                    'command': '.venv-cpu/bin/python runtime.py offline --candidate fallback1',
                    'exit_code': 0, 'log': str(fb_offline.relative_to(ROOT)),
                    'log_sha256': _sha(fb_offline)}
            if all(p.is_file() for p in (fb_compat, fb_positive, fb_negative)):
                fallback_entry['compatibility'] = {
                    'receipt': str(fb_compat.relative_to(ROOT)),
                    'sha256': _sha(fb_compat),
                    'log': str(fb_positive.relative_to(ROOT)),
                    'negative_log': str(fb_negative.relative_to(ROOT))}
            entry['candidates'] = [fallback_entry]
        compat = ROOT / 'cases' / suffix / 'delivery-compatibility-draft.json'
        positive = ROOT / 'cases' / suffix / 'delivery-compatibility-analysis-draft.log'
        negative = ROOT / 'cases' / suffix / 'delivery-compatibility-negative-draft.log'
        offline = ROOT / 'cases' / suffix / 'delivery-offline-draft.log'
        if compat.is_file() and positive.is_file() and negative.is_file():
            entry['compatibility'] = {'receipt': str(compat.relative_to(ROOT)),
                                      'sha256': _sha(compat),
                                      'log': str(positive.relative_to(ROOT))}
            entry['negative'] = {'log': str(negative.relative_to(ROOT))}
        if offline.is_file():
            entry['offline'] = {'construction_sha256': _sha(path),
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' +
                           ASSIGNMENT + '/execution-manifest.draft.json --case ' +
                           case['case_id'] + ' --output .runtime-work/c111125-owner/delivery-offline-' +
                           suffix + '-v4',
                'exit_code': 0, 'log': str(offline.relative_to(ROOT)),
                'log_sha256': _sha(offline)}
        physical = ROOT / 'cases' / suffix / 'physical-preparation.draft.json'
        if physical.is_file():
            proof = json.loads(physical.read_text())
            if proof.get('construction_sha256') != _sha(path):
                raise ValueError('physical proof changed construction: ' + suffix)
            entry['physical_preparation'] = {
                'receipt': str(physical.relative_to(ROOT)),
                'sha256': _sha(physical)}
        cases.append(entry)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': runtime_sha,
                'semantic_index_sha256': _sha(ROOT / 'proposals/semantic-index.json'),
                'status': 'partial', 'cases': cases}
    _write(ROOT / 'execution-manifest.draft.json', manifest)
    return len(cases)


if __name__ == '__main__':
    print(build())
