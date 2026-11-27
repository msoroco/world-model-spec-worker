"""Materialize the two exact selected Native construction bundles."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
SOURCE_FILES = ('runner.py', 'geometry.py', 'parking_saved_measure.py',
                'source_review.py', 'finalize.py', 'tests/test_native.py')
CHANNELS = ('dev.zone_sign', 'dev.regulatory_sign', 'dev.governs',
            'drv.standing_or_parked', 'rel.occupies', 'st.lane_width')


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    recording = {
        'channels': [
            {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'Original Native road, actor and frame map joined to independently cited device, width and governed-extent review',
             'time_window': 'all 600 original parking frames',
             'reference_frame': 'Native narrow-road coordinates',
             'uncertainty': 'OpenDRIVE request alone cannot prove official authority, legal narrowness, sign visibility or parking purpose'}
            for name in CHANNELS],
        'context_inputs': [],
        'limitations': [
            '2.8 m requested lane width has no statutory cutoff and needs source-backed narrow-highway classification',
            'OpenDRIVE sign request does not prove official authority, actual erection or a governed extent',
            'stationary velocity is an engineering observation, not legal parking']}
    for suffix in ('probe_01', 'probe_02'):
        directory = HERE / 'cases' / suffix
        config_path = directory / 'config.json'
        config = json.loads(config_path.read_text())
        config['recording_description'] = recording
        config['case'] = {'case_id': config['case_id'], 'recording_description': recording}
        write(config_path, config)
        files = [{'path': name, 'content': (HERE / name).read_text()} for name in SOURCE_FILES]
        files.append({'path': 'config.json', 'content': config_path.read_text()})
        construction = {
            'format': 'worker-inline-construction',
            'case_id': config['case_id'], 'law_id': config['law_id'],
            'cell_id': config['cell_id'], 'actor': config['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': recording,
            'measurement_plan': {
                'entrypoint': 'finalize.py',
                'required_sources': ['road.xodr', 'road-context.json', 'road-review.json',
                                     'vehicle-pose.jsonl', 'video_frames.jsonl',
                                     'trace.jsonl', 'capture/evidence.jsonl',
                                     'source_context/highway.txt',
                                     'source_context/narrow_designation.txt',
                                     'source_context/official_authority.txt',
                                     'source_context/device_erection.txt',
                                     'source_context/device_content.txt',
                                     'source_context/governed_extent.txt'],
                'source_review_required': True},
            'static_checks': ['Two 2.8-m driving lanes and 140-m road with a prohibitory OpenDRIVE signal',
                              'Parked-vehicle target 35 m beyond or 0 m within requested governed x interval',
                              'Four synchronized 20-Hz cameras for 600 frames'],
            'mechanisms': ['OpenDRIVE road and no-parking signal request with Native readback',
                           'Actor held under brake/handbrake at selected location; original footprint and speed recorded',
                           'Original road/device authority, erection and extent joined from independent source review'],
            'termination_rules': ['600 original Native frames',
                                  'Destroy locally owned actors and restore Native world'],
            'status': 'cpu_construction_physical_unverified'}
        write(directory / 'construction.json', construction)
        if suffix == 'probe_01':
            write(HERE / 'config.json', config)
            write(HERE / 'construction.json', construction)
    print(json.dumps({'cases': [ASSIGNMENT + '__probe_01', ASSIGNMENT + '__probe_02']}))


if __name__ == '__main__':
    main()
