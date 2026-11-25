"""Build four exact source-gated inline constructions; no site is fabricated."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
MODULES = (
    'runner.py', 'native_backing_lifecycle.py', 'native_backing.py',
    'native_backing_capture.py', 'backing_controller.py', 'backing_geometry.py',
    'backing_measurements.py', 'backing_semantics.py', 'saved_backing.py',
    'traffic_lifecycle.py', 'traffic_native.py', 'traffic_capture.py',
    'traffic_controller.py', 'traffic_geometry.py', 'traffic_measurements.py',
    'traffic_semantics.py', 'traffic_saved.py',
    'saved_comparison.py', 'media_decode.py',
    'tests/test_bundle.py')


def build():
    proposals = json.loads((HERE / 'proposals/cases.json').read_text())
    plans = {row['case_id']: row for row in proposals['cases']
             if row['target_type'] != 'baseline'}
    expected = {AID + '__' + suffix for suffix in (
        'pedestrian_yield', 'pedestrian_continue', 'traffic_yield', 'traffic_continue')}
    if set(plans) != expected:
        raise ValueError('selected construction cases differ from frozen plan')
    base_config = json.loads((HERE / 'config.json').read_text())
    outputs = []
    for case_id in sorted(expected):
        suffix = case_id.removeprefix(AID + '__')
        config = dict(base_config, selected_case_id=case_id,
                      case={'case_id': case_id,
                            'recording_description': plans[case_id]['recording_description']})
        files = [{'path': path, 'source': 'work/' + AID + '/' + path,
                  'content': (HERE / path).read_text()} for path in MODULES]
        analysis = 'traffic_analysis.py' if suffix.startswith('traffic_') else 'analysis.py'
        files.append({'path': 'analysis.py', 'source': 'work/' + AID + '/' + analysis,
                      'content': (HERE / analysis).read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        value = {
            'status': 'draft', 'law_id': 'NRS-484B-113-3', 'cell_id': 'C111301',
            'actor': 'motor_vehicle_driver', 'case_id': case_id,
            'candidate_id': 'primary', 'entrypoint': 'runner.py', 'files': files,
            'recording_description': plans[case_id]['recording_description'],
            'mechanisms': {
                'construction_status': 'source_gated_native_backing',
                'actors': 'reviewed original backing vehicle and pedestrian or moving-traffic vehicle blueprint/pose by exact case',
                'controller': 'yield hold/brake or continued reverse by exact case and conflict participant',
                'cameras': 'four reviewed original extrinsics at 20 Hz; original map bytes required',
                'native_extraction': 'runtime PipelineCapture same-tick original actor telemetry, evidence, graph and CARLA recorder; joined to four source cameras'},
            'measurement_plan': [{
                'case_id': case_id, 'analysis_entrypoint': 'analysis.py',
                'original_native_inputs': ['map.json', 'road.xodr', 'telemetry.json',
                                           'frame-map.json', 'acquisition.json',
                                           'carla_recorder.log', 'capture/manifest.json',
                                           'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                                           'overview.mkv', 'approach.mkv',
                                           'reference_corner.mkv', 'driver_reference.mkv'],
                'judgment_status': 'unresolved'}],
            'static_checks': [{'name': 'exact-case source-gated runner',
                               'source': 'runner.py --check and tests/test_bundle.py',
                               'status': 'passed'}],
            'termination_rules': [
                'Capture exactly 900 consecutive original 20 Hz world frames or fail.',
                'Release owned actors and sensors and restore world settings before acquisition publication.']}
        target = HERE / ('construction.json' if suffix == 'pedestrian_yield'
                         else 'construction-' + suffix + '.json')
        target.write_text(json.dumps(value, indent=2) + '\n')
        outputs.append(target.name)
    return outputs


if __name__ == '__main__':
    print(json.dumps(build()))
