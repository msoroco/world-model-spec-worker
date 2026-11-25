"""Build source-gated selected manifest from exact C111329 constructions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')

def build():
    draft = json.loads((ROOT / 'execution-manifest.cpu-draft.json').read_text())
    for entry in draft['cases']:
        suffix = entry['case_id'].split('__')[-1]
        primary = json.loads((ROOT / entry['construction']).read_text())
        fallback = json.loads(json.dumps(primary))
        runner = next(x for x in fallback['files'] if x['path'] == 'runner.py')
        old = "spawn_z=bindings['spawn_z'])"
        assert runner['content'].count(old) == 1
        runner['content'] = runner['content'].replace(old, "spawn_z=bindings['spawn_z'], speed_mps=1.0)")
        runner.pop('source', None)
        rel = f'cases/{suffix}/fallback1-construction.json'
        put(ROOT / rel, fallback)
        entry['kind'] = 'delivery'
        entry['candidate_risk'] = {'status': 'physical', 'reason':
            'Original intersection route reachability and device readback are unmeasured; endpoint settling may fail.'}
        entry['candidates'] = [{'id': 'fallback1', 'construction': rel,
            'construction_sha256': digest(ROOT / rel),
            'trigger': {'source': 'original 20 Hz walker center history',
                        'metric': 'distance to surveyed pedestrian destination',
                        'failure_condition': 'primary control fails to settle at the surveyed destination'},
            'changed_knobs': ['walker requested speed from 1.2 to 1.0 m/s']}]
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['original_source_gate'] = {
            'required_at_execution': True,
            'map_and_corners': 'surveyed original C111329 intersection polygon and four pedestrian corners',
            'device_and_instruction': 'official pedestrian device identity, placement and diagonal instruction record',
            'exception': 'review original NRS 484B.290 exception source before legal conclusion',
            'original_media': '900 synchronized original frames from four cameras with frame and pixel review',
            'source_status': 'unresolved', 'physical_completion_claimed': False,
            'legal_conclusion': 'not_assessed'}
        entry['acquisition'] = {
            'walker_center_xy': {'entrypoint': 'native_acquisition.py', 'method': 'original walker pose per synchronous frame'},
            'device_readback': {'entrypoint': 'native_acquisition.py', 'method': 'source-bound pedestrian device state per synchronous frame'},
            'camera_frame_join': {'entrypoint': 'capture_export.py', 'method': 'four original camera frame identities and PNG hashes'}}
    draft['status'] = 'selected_source_gated_originals_pending'
    draft['source_audit_protocol'] = {
        'positive': 'verify SHA-bound original map/corner and pedestrian device records, case route, instruction, and NRS 484B.290 review before Native dispatch',
        'negative': 'reject changed source bytes, missing official diagonal instruction, mismatched case or incomplete original camera frames',
        'diagnostics': 'synthetic test doubles exercise interface only; none are original sources'}
    draft['comparison_audit_protocol'] = {
        'controls': 'three exact planned case contrasts, joined on C111329 and NRS 484B.287(1)(d)',
        'positive': 'independently compare case measurements only after original source and physical completion audits',
        'negative': 'reject mismatched cell, law, recording source or changed case measurements'}
    put(ROOT / 'execution-manifest.json', draft)

if __name__ == '__main__':
    build()
    print('canonical source-gated manifest and four speed fallbacks built')
