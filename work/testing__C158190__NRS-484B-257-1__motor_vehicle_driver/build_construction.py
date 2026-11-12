"""Refresh the inline first-case construction after reviewed source edits."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FILES = ('runner.py', 'camera_setup.py', 'camera_encoder.py', 'yield_site.py',
         'yield_construction.py', 'yield_controller.py', 'yield_motion.py',
         'yield_capture_sources.py', 'yield_control_sources.py',
         'yield_interaction_sources.py', 'yield_context.py',
         'yield_measurements.py', 'finalizer.py', 'prepare_review.py',
         'native-map-plan/yield-nearest-view.xodr',
         'tests/test_runner.py', 'tests/test_yield_site.py',
         'tests/test_yield_construction.py', 'tests/test_yield_controller.py',
         'tests/test_yield_motion.py', 'tests/test_yield_capture_sources.py',
         'tests/test_yield_control_sources.py',
         'tests/test_yield_interaction_sources.py',
         'tests/test_yield_context.py', 'tests/test_finalizer.py',
         'tests/test_prepare_review.py',
         'tests/test_yield_measurements.py', 'config.json')


def main():
    config = json.loads((ROOT / 'config.json').read_text())
    files = []
    for name in FILES:
        source = ROOT / name
        files.append({'path': name, 'content': source.read_text(),
                      'source': str(source.relative_to(REPO))})
    construction = {
        'case_id': config['selected_case_id'],
        'law_id': config['law_id'], 'cell_id': config['cell_id'],
        'actor': config['actor'], 'entrypoint': 'runner.py',
        'status': 'draft', 'recording_description': config['recording_description'],
        'measurement_plan': {'raw_sources': ['trace.jsonl', 'approach_history.jsonl',
                                             'visibility_rays.jsonl', 'visibility_samples.json',
                                             'video_frames.jsonl', 'road_context.json',
                                             'control_inventory.jsonl',
                                             'interaction_history.jsonl',
                                             'control_context.json',
                                             'rendered_marking_review.json',
                                             'capture/native_map_facts.json'],
                             'analysis': 'finalizer.py',
                             'legal_conclusion': 'unresolved'},
        'static_checks': [{'name': 'runner_check', 'status': 'passed',
                           'method': 'materialized --check and C158190 CPU tests'}],
        'termination_rules': ['30 seconds at 20 Hz',
                              'abort on missing source-camera frame or off-route actor',
                              'seal only after encoder closure and verified world restoration'],
        'mechanisms': ['authored yield-sign one-way-to-two-way OpenDRIVE junction',
                       'exact-case ego and through actor staging',
                       'Native pre-tick motion controls',
                       'four synchronized lossless source-camera streams',
                       'original sight rays, control inventory, actor bodies, trace, graph and frame map',
                       'saved-only hash-bound camera review and finalization'],
        'files': files,
    }
    (ROOT / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    print(json.dumps({'case_id': construction['case_id'], 'files': len(files),
                      'status': 'draft'}))


if __name__ == '__main__':
    main()
