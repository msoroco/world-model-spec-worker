"""Build selected inline cases; no synthetic source is promoted to original."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
CAMERAS = [('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    ids = [c['case_id'] for c in plan['cases']]
    common = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'], 'actor': plan['actor'],
              'candidate_id': 'primary', 'rate_hz': 20, 'duration_s': 45,
              'required_atoms': [], 'source_packets': [], 'supported_case_ids': ids,
              'cameras': [{'name': name, 'width': w, 'height': h, 'fov_deg': 75,
                           'pose_strategy': 'reviewed stop, full bus body and designation evidence'}
                          for name, w, h in CAMERAS]}
    for case in plan['cases']:
        suffix = case['case_id'].split('__')[-1]
        folder = ROOT / 'cases' / suffix
        recording = {'channels': [
            {'name': 'bus_stopped_interval', 'unit': 's', 'method': 'source-sealed Native frame and independent activity transition join', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original frame/time', 'uncertainty': 'activity transition review'},
            {'name': 'applicable_designated_duration', 'unit': 's', 'method': 'independently reviewed City Traffic Engineer designation and governing conditions', 'sampling_rate_hz': 20, 'time_window': 'entire stop event', 'reference_frame': 'source reviewed designation', 'uncertainty': 'applicability review'},
            {'name': 'body_inside_stop', 'unit': 'bool', 'method': 'Native bus footprint versus reviewed bus-stop boundary', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original frame/time', 'uncertainty': 'map and body localization'},
            {'name': 'four_camera_frame_identity', 'unit': 'frame ID', 'method': 'four synchronized RGB cameras', 'sampling_rate_hz': 20, 'time_window': 'all 900 frames', 'reference_frame': 'original frame/time', 'uncertainty': 'pixel review'}],
            'context_inputs': [{'name': 'reviewed_site_and_designation', 'unit': 'structured original record', 'method': 'source-hashed official designation, stop boundary and conditions'}, {'name': 'bus_operator_and_activity', 'unit': 'structured original record', 'method': 'source-hashed non-tour bus/operator and independent activity review'}],
            'limitations': ['Synthetic D=15 s diagnostics are not original designation or legal acceptance.']}
        config = dict(common)
        config['selected_case_id'] = case['case_id']
        config['case'] = {'case_id': case['case_id'], 'conduct': case['conduct'],
                          'duration_relation': case['duration_relation'],
                          'duration_request': case['duration_request'],
                          'diagnostic_designated_duration_s': 15,
                          'diagnostic_duration_s': case['diagnostic_duration_s'],
                          'recording_description': recording}
        scene = {'case_id': case['case_id'], 'cell_id': 'C393262',
                 'actor': 'bus_driver', 'source_kind': 'synthetic_diagnostic_fixture',
                 'conduct': case['conduct'], 'duration_relation': case['duration_relation']}
        write(folder / 'config.json', config)
        write(folder / 'scene.json', scene)
        entries = []
        for name, source in [('runner.py', ROOT / 'runner.py'),
                             ('bus_duration.py', ROOT / 'bus_duration.py'),
                             ('native_capture.py', ROOT / 'native_capture.py'),
                             ('assemble_reviewed_activity.py', ROOT / 'assemble_reviewed_activity.py'),
                             ('analysis.py', ROOT / 'analysis.py'),
                             ('tests/test_bundle.py', ROOT / 'tests/test_bundle.py'),
                             ('config.json', folder / 'config.json'),
                             ('scene.json', folder / 'scene.json')]:
            entries.append({'path': name, 'source': str(source.relative_to(ROOT.parents[1])),
                            'content': source.read_text()})
        construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'], 'actor': plan['actor'],
                        'case_id': case['case_id'], 'entrypoint': 'runner.py',
                        'recording_description': recording, 'files': entries,
                        'measurement_plan': {
                            'bus_identity': 'source-hashed non-tour bus and covered operator',
                            'stop_designation': 'official location-specific City Traffic Engineer duration and conditions',
                            'activity_interval': 'independent start/end review joined to 900 Native bus footprint frames',
                            'duration_relation': 'observed uninterrupted interval versus actual D; no legal verdict'},
                        'static_checks': ['exact C393262 case/config selection',
                                          'reviewed original site and designation SHA-256 before Native spawn',
                                          '900 synchronized frames and four camera sources'],
                        'termination_rules': ['stop at 900 Native ticks',
                                              'fail on incomplete bus interval or source/camera mismatch'],
                        'mechanisms': ['reviewed original Native map and bus-stop site',
                                       'non-tour bus with approach, stopped interval and departure',
                                       'four synchronized RGB cameras',
                                       'saved original bus footprint and velocity samples']}
        write(folder / 'construction.json', construction)
    for name in ('config.json', 'scene.json', 'construction.json'):
        (ROOT / name).write_text((ROOT / 'cases/park_below' / name).read_text())
    print('six exact inline constructions generated')


if __name__ == '__main__':
    build()
