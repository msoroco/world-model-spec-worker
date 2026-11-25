"""Build two exact source-bound U-turn CPU constructions."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
SUFFIXES = ('source_verified_single_movement_uturn',
            'source_verified_multiple_movement_uturn')
MODULES = ('runner.py', 'uturn_route.py', 'barrier_construction.py',
           'native_capture.py', 'camera_encoder.py', 'uturn_measurements.py',
           'saved_finalizer.py')


def _case(suffix):
    case = ASSIGNMENT + '__' + suffix
    folder = ROOT / 'cases' / suffix
    config = json.loads((folder / 'config.json').read_text())
    channels = [
        {'name': name, 'unit': unit, 'method': method, 'sampling_rate_hz': 20,
         'time_window': '30 seconds at 20 Hz',
         'reference_frame': 'original Native tick and four cameras',
         'uncertainty': 'actual motion, authority status and legal judgment require independent review'}
        for name, unit, method in (
            ('ego_body', 'm', 'original complete Native world vertices'),
            ('other_body', 'm', 'original complete Native world vertices'),
            ('ego_heading', 'degrees', 'original Native pose yaw'),
            ('divider_overlap', 'boolean', 'complete body against sourced divider polygon'),
            ('camera_frames', 'frame', 'four original RGB frames joined to Native tick'),
            ('ego_gear', 'categorical', 'original Native reverse-control readback'))]
    recording = {'channels': channels, 'context_inputs': [
        {'name': 'divider_site', 'unit': 'structured record',
         'method': 'source-hashed divided-road, opening and authority context',
         'source_refs': ['divider_context.json', 'site_source_receipt.json'],
         'uncertainty': 'public-authority establishment requires independent document review'},
        {'name': 'barrier_opening', 'unit': 'structured record',
         'method': 'realized Native barrier section vertices and opening',
         'source_refs': ['barrier_receipt.json'],
         'uncertainty': 'actual clearance requires physical review'}],
        'limitations': ['Authored CPU site is diagnostic only; original authority and map review pending']}
    config['case'] = {'case_id': case, 'recording_description': recording}
    config_path = ROOT / 'config.json' if suffix == SUFFIXES[0] else folder / 'config.json'
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    files = []

    def add(source, destination):
        files.append({'path': destination, 'source': source.relative_to(REPO).as_posix(),
                      'content': source.read_text()})

    for name in MODULES:
        add(ROOT / name, name)
    for test in sorted((ROOT / 'tests').glob('test*.py')):
        add(test, 'tests/' + test.name)
    add(config_path, 'config.json')
    for name in ('site-plan.json', 'route-plan.json', 'diagnostic-site.json',
                 'diagnostic-authority.txt'):
        add(folder / name, name)
    for variant in SUFFIXES:
        for name in ('site-plan.json', 'route-plan.json', 'diagnostic-site.json',
                     'diagnostic-authority.txt'):
            add(ROOT / 'cases' / variant / name, 'cases/' + variant + '/' + name)
    construction = {
        'case_id': case, 'law_id': 'NRS-484B-227-1', 'cell_id': 'C126120',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
        'status': 'partial_cpu_diagnostic_unreviewed_native_site',
        'files': files, 'recording_description': recording,
        'measurement_plan': {'raw_sources': [
            'road.xodr', 'trace.jsonl', 'carla_recorder.log', 'capture/manifest.json',
            'divider_context.json', 'barrier_receipt.json', 'site_source_receipt.json',
            'movement_history.jsonl', 'video_frames.jsonl', 'control_history.jsonl',
            'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'],
            'analysis_entrypoint': 'saved_finalizer.py',
            'saved_processing_status': 'authored; exact runtime proof pending'},
        'static_checks': ['runner --check validates both exact routes without CARLA',
                          'CPU tests reject blocked divider and disconnected gear phases'],
        'termination_rules': ['600 original frames at 20 Hz',
                              'close encoders and capture before Native owner release',
                              'restore world with readback before capture seal'],
        'mechanisms': ['source-gated Native site, authority and camera review',
                       'two realized barrier sections around one opening',
                       'segmented single or forward-reverse-forward U-turn controller',
                       'four original FFV1 cameras, Native gear/body history and FrameMap',
                       'PipelineCapture telemetry and graph sources']}
    destination = ROOT / 'construction.json' if suffix == SUFFIXES[0] else folder / 'construction.json'
    destination.write_text(json.dumps(construction, indent=2) + '\n')


def build():
    for suffix in SUFFIXES:
        _case(suffix)


if __name__ == '__main__':
    build()
