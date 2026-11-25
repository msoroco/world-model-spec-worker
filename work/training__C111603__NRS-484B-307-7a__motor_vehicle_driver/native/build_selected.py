"""Bind exact flashing-arrow selected Native bundles to retained diagnostics."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SELECTED = ('controlled_1', 'controlled_2', 'pedestrian_clearance',
            'pedestrian_overlap', 'concurrent_absent', 'concurrent_present')
SOURCE_TERMS = ('dev.traffic_signal', 'dev.governs', 'st.lane_enters',
                'drv.turning', 'drv.entering_intersection', 'kin.speed',
                'ru.pedestrian', 'st.crosswalk', 'drv.in_intersection',
                'drv.yields_to', 'drv.time_to_conflict')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def channel(name):
    if name in SOURCE_TERMS:
        return {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                'method': 'per-frame original source references for independent review; no legal classification',
                'time_window': '600 frames / 30 seconds',
                'reference_frame': 'original world and frame time',
                'uncertainty': 'Observation and lawful status remain unverified'}
    return {'name': name, 'unit': 'video' if name == 'four_camera_video' else 'structured', 'sampling_rate_hz': 20,
            'method': 'source-joined original Native actor history and four synchronized cameras',
            'time_window': '600 frames / 30 seconds',
            'reference_frame': 'original world and frame time',
            'uncertainty': 'Actual arrow pixels and legal status require independent review'}


def build():
    output = []
    for case, source in (('controlled_1', 'primary'), ('controlled_2', 'contrast')):
        base = json.loads((ROOT / f'current-v2-{source}-construction.json').read_text())
        recording = {'channels': [channel(x) for x in
                                  ('ego_motion', 'other_motion', 'arrow_request',
                                   'turn_history', 'four_camera_video', *SOURCE_TERMS)],
                     'context_inputs': [
                         {'name': 'source_law_and_signal_governance', 'unit': 'structured',
                          'method': 'source-hashed exact law and signal-request context; governance review pending'},
                         {'name': 'lawful_status_review', 'unit': 'structured',
                          'method': 'saved source review fields remain pending; no legal label'}],
                     'limitations': ['Controller request is not arrow governance or lawful status.',
                                     'Original source pixels, pedestrian status and cautiousness require independent review.']}
        base['status'] = 'selected_delivery_prepared'
        base['static_checks'] = [
            'exact selected case identity and frozen source bindings',
            '600 synchronized frames and four full-profile camera sources',
            'source-joined participant and signal-request histories',
            'lawful status, arrow governance and cautiousness remain review pending']
        base['termination_rules'] = [
            'complete 600 synchronized Native frames and close all encoders',
            'otherwise report explicit capture failure and restore original world state']
        base['recording_description'] = recording
        base['measurement_plan'] = ('Join original 600-frame ego/other motion, requested signal '
                                    'state and four source videos; retain lawful status and '
                                    'cautiousness as unverified.')
        base['mechanisms'] = ['30-second synchronous Native capture',
                              'two actor controller requests with controlled ego release',
                              'four original full-profile camera sources',
                              'source-bound saved-only measurement']
        existing = {f['path']: f for f in base['files']}
        common = {
            'runner.py': (ROOT / 'native/native_runner.py').read_text(),
            'finalize.py': (ROOT / 'native/finalize_selected.py').read_text(),
        }
        for candidate in ('primary', 'fallback1'):
            construction = copy.deepcopy(base)
            config = json.loads(existing['config.json']['content'])
            config.update(case_id=AID + '__' + case,
                          selected_case_id=AID + '__' + case,
                          supported_case_ids=[AID + '__' + key for key in SELECTED],
                          cell_id='C111603', law_id='NRS-484B-307-7a',
                          actor='motor_vehicle_driver', candidate_id=candidate,
                          duration_s=30, rate_hz=20,
                          ego_release_frame=320 if case == 'controlled_1' else 200,
                          ego_throttle=0.22 if candidate == 'primary' else 0.28,
                          other_throttle=0.18,
                          pedestrian_lawful_status=None,
                          other_traffic_lawful_status=None,
                          cautiousness_legal_judgment=None,
                          recording_description=recording,
                          cameras=[{'name': name, 'width': width, 'height': height,
                                    'fps': 20, 'fov_deg': 90,
                                    'location_xyz_m': xyz,
                                    'rotation_pyr_deg': pyr,
                                    'pose_strategy': ('fixed_relative_to_subject_vehicle'
                                                      if name == 'driver_reference'
                                                      else 'fixed_scene_overview_of_travel')}
                                   for name, width, height, xyz, pyr in (
                                       ('overview', 1920, 1080, [0, 0, 28], [-75, 0, 0]),
                                       ('approach', 1280, 720, [0, 0, 2.4], [-5, 0, 0]),
                                       ('reference_corner', 1280, 720, [2, 1, 1.8], [-12, -45, 0]),
                                       ('driver_reference', 1280, 720, [0, 0, 1.8], [-10, 0, 0]))])
            contents = dict(common, **{'config.json': json.dumps(config, indent=2) + '\n'})
            for item in construction['files']:
                if item['path'] in contents:
                    item['content'] = contents.pop(item['path'])
            for path, content in contents.items():
                construction['files'].append({'path': path, 'content': content})
            path = ROOT / f'native/selected-{case}-{candidate}-construction.json'
            dump(path, construction)
            output.append({'case': case, 'candidate': candidate,
                           'construction': str(path.relative_to(ROOT)),
                           'sha256': sha(path)})
    root = json.loads((ROOT / 'native/selected-controlled_1-primary-construction.json').read_text())
    for item in root['files']:
        destination = ROOT / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(item['content'])
    dump(ROOT / 'construction.json', root)
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    build()
