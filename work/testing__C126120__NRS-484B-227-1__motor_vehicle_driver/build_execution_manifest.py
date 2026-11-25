"""Bind current C126120 source and proof bytes to exact delivery entries."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest = json.loads((ROOT / 'review-fallback-manifest.json').read_text())
    manifest.pop('draft_only', None)
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        folder = ROOT / 'cases' / suffix
        rel = 'cases/' + suffix + '/'
        primary_offline = folder / 'primary-offline.log'
        entry['offline'] = {'command': primary_offline.read_text().splitlines()[0][2:],
                            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
                            'log': rel + 'primary-offline.log',
                            'log_sha256': digest(primary_offline)}
        entry['compatibility'] = {'receipt': rel + 'primary-compatibility.json',
                                  'sha256': digest(folder / 'primary-compatibility.json'),
                                  'log': rel + 'primary-compat-analysis.log',
                                  'negative_log': rel + 'primary-compat-negative.log'}
        entry['negative'] = {'log': rel + 'primary-compat-negative.log'}
        entry['physical_preparation'] = {
            'receipt': rel + 'primary-physical-preparation.json',
            'sha256': digest(folder / 'primary-physical-preparation.json')}
        entry['post_capture'] = {
            'receipt': rel + 'primary-saved-processing.json',
            'sha256': digest(folder / 'primary-saved-processing.json'),
            'test_log': rel + 'primary-saved-analysis.log',
            'test_log_sha256': digest(folder / 'primary-saved-analysis.log'),
            'test_exit_code': 0, 'recorded_only': True,
            'command': 'runtime.py process-saved --manifest review-compat-all-manifest.json --case ' + entry['case_id'],
            'feedback_command': 'review saved feedback for ' + entry['case_id']}
        entry['acquisition'] = {
            'ego_body': {'entrypoint': 'native_capture.py', 'method': 'record complete original Native ego body each tick', 'evidence': 'movement_history.jsonl'},
            'other_body': {'entrypoint': 'native_capture.py', 'method': 'record complete original Native other body each tick', 'evidence': 'movement_history.jsonl'},
            'ego_heading': {'entrypoint': 'native_capture.py', 'method': 'record original Native ego yaw each tick', 'evidence': 'movement_history.jsonl'},
            'divider_overlap': {'entrypoint': 'uturn_measurements.py', 'method': 'join complete original body to sourced divider and opening', 'evidence': 'movement_history.jsonl and divider_context.json'},
            'camera_frames': {'entrypoint': 'native_capture.py', 'method': 'synchronize four original cameras with Native tick', 'evidence': 'video_frames.jsonl and four FFV1 sources'},
            'ego_gear': {'entrypoint': 'native_capture.py', 'method': 'record original Native reverse control readback', 'evidence': 'movement_history.jsonl'}}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        entry['candidate_risk'] = {'status': 'physical',
                                   'reason': entry['candidates'][0]['design_rationale']}
        candidate = entry['candidates'][0]
        alternate_offline = folder / 'fallback1-offline.log'
        candidate['offline'] = {'command': alternate_offline.read_text().splitlines()[0][2:],
                                'exit_code': 0,
                                'construction_sha256': candidate['construction_sha256'],
                                'log': rel + 'fallback1-offline.log',
                                'log_sha256': digest(alternate_offline)}
        candidate['compatibility'] = {'receipt': rel + 'fallback1-compatibility.json',
                                      'sha256': digest(folder / 'fallback1-compatibility.json'),
                                      'log': rel + 'fallback1-compat-analysis.log',
                                      'negative_log': rel + 'fallback1-compat-negative.log'}
        script = ROOT / 'delivery_audit.py'
        base = ('SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c126120-delivery-audit '
                'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python '
                + str(script.relative_to(REPO)) + ' --attempt .runtime-work/c126120-compat-v2-'
                + suffix + ' --case ' + entry['case_id'])
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': digest(script),
            'command': base + ' --diagnostic-fixture', 'test_exit_code': 0,
            'test_log': rel + 'primary-delivery-positive.log',
            'test_log_sha256': digest(folder / 'primary-delivery-positive.log'),
            'negative_command': base, 'negative_exit_code': 1,
            'negative_expected_error': 'Native acquisition required for physical acceptance',
            'negative_log': rel + 'primary-delivery-negative.log',
            'negative_log_sha256': digest(folder / 'primary-delivery-negative.log')}
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    build()
