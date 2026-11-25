"""Bind three blind-junction reference branches to exact CPU constructions."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = ('stop_line_other_inside', 'crosswalk_other_previously_stopped',
            'nearest_view_other_inside', 'stop_line_no_halt',
            'stop_line_other_previously_stopped')
MODULES = ('runner.py', 'native_inoperative_control.py', 'native_site_contract.py',
           'native_stop_sources.py', 'saved_finalizer.py',
           'inoperative_stop_measurements.py', 'inoperative_stop.py',
           'signal_control.py')


def build():
    for suffix in SUFFIXES:
        folder = ROOT / 'cases' / suffix
        config_path = ROOT / 'config.json' if suffix == SUFFIXES[0] else folder / 'config.json'
        config = json.loads(config_path.read_text())
        files = []

        def add(path, destination):
            files.append({'path': destination,
                          'source': path.relative_to(REPO).as_posix(),
                          'content': path.read_text()})

        add(config_path, 'config.json')
        for name in ('site-review.json', 'site-sources.json',
                     config['site']['native_map_xodr']['path']):
            path = ROOT / name if suffix == SUFFIXES[0] else folder / name
            add(path, name)
        for name in MODULES:
            add(ROOT / name, name)
        for test in sorted((ROOT / 'tests').glob('test*.py')):
            if test.name in ('test_runner_plan.py', 'test_delivery_audit.py'):
                # These package tests compare candidates or run the independent
                # auditor, which is outside each selected Native bundle.
                continue
            add(test, 'tests/' + test.name)
        construction = {
            'case_id': config['selected_case_id'], 'law_id': config['law_id'],
            'cell_id': config['cell_id'], 'actor': config['actor'],
            'entrypoint': 'runner.py', 'status': 'authored_cpu_candidate',
            'recording_description': config['recording_description'],
            'files': files,
            'measurement_plan': {
                'raw_sources': ['road.xodr', 'trace.jsonl', 'capture/manifest.json',
                                'vehicle_signal_history.jsonl', 'video_frames.jsonl',
                                'junction_context.json', 'overview.mkv', 'approach.mkv',
                                'reference_corner.mkv', 'driver_reference.mkv'],
                'analysis_entrypoint': 'saved_finalizer.py',
                'saved_processing_status': 'authored; exact runtime proof pending'},
            'static_checks': ['runner --check verifies source-bound site and selected stop hierarchy',
                              'CPU tests reject operating or uninventoried heads'],
            'termination_rules': ['45-second, 20 Hz original Native capture',
                                  'close cameras and capture before world restoration and seal'],
            'mechanisms': ['two-actor sourced approaches and stop/release control',
                           'all inventoried installed signal heads Off with Native readback',
                           'four original synchronized cameras and complete actor body history',
                           'saved-only finalizer and original-frame stop/priority observations']}
        target = ROOT / 'construction.json' if suffix == SUFFIXES[0] else folder / 'construction.json'
        target.write_text(json.dumps(construction, indent=2) + '\n')


if __name__ == '__main__':
    build()
