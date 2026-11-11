"""Bind exact daylight and adjacent-shoulder Native construction probes."""

from hashlib import sha256
import json
from pathlib import Path

from build_night_probes import SOURCE_FILES
from native_headlamp_probe import CONTEXT_CASES, check_config


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def build():
    base = json.loads((HERE / 'probe-config.json').read_text())
    cases = []
    for case_id, (gap_ft, uppermost, time_applies, position) in CONTEXT_CASES.items():
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        config = {**base, 'selected_case_id': case_id,
                  'requested_gap_ft': gap_ft,
                  'requested_uppermost_distribution': uppermost,
                  'requested_lighting_time_applies': time_applies,
                  'requested_roadway_position': position}
        check_config(config)
        config_bytes = (json.dumps(config, indent=2) + '\n').encode()
        config_rel = f'context-probes/{suffix}-config.json'
        construction_rel = f'context-probes/{suffix}-construction.json'
        (HERE / config_rel).parent.mkdir(parents=True, exist_ok=True)
        (HERE / config_rel).write_bytes(config_bytes)
        files = [{'path': 'config.json', 'content': config_bytes.decode()}]
        files.extend({'path': name, 'content': (HERE / name).read_text()}
                     for name in SOURCE_FILES)
        construction = {
            'format': 'worker-inline-construction', 'case_id': case_id,
            'cell_id': 'C178038', 'law_id': 'NRS-484D-215-2',
            'actor': 'motor_vehicle_driver',
            'entrypoint': 'native_headlamp_probe.py',
            'recording_description': config['case']['recording_description'],
            'files': files,
            'measurement_plan': {'original_rows': ['following_footprints.jsonl',
                                                   'headlamp_readbacks.jsonl',
                                                   'roadway_environment.jsonl',
                                                   'lighting_context.json'],
                                 'saved_finalizer': 'headlamp_finalizer.py',
                                 'legal_judgment': None},
            'static_checks': ['native_headlamp_probe.py --check --config config.json'],
            'termination_rules': ['80 original 20 Hz frames or fail'],
            'mechanisms': ['CARLA connected same-lane route',
                           'explicit authored lighting-time premise',
                           'Native waypoint lane-type and sun-angle readback',
                           'four synchronized original RGB streams'],
        }
        construction_bytes = (json.dumps(construction, indent=2) + '\n').encode()
        (HERE / construction_rel).write_bytes(construction_bytes)
        cases.append({'case_id': case_id, 'construction': construction_rel,
                      'construction_sha256': sha256(construction_bytes).hexdigest(),
                      'physical_risk': {
                          'trigger': 'No connected adjacent shoulder or recorded context/beam does not match authored setup.',
                          'observable': 'Native lane type, sun angle, full body gap and lamp readback.',
                          'response': 'Retain failed attempt and revise map placement or context; do not infer civil time from sun angle.'}})
    manifest = {'format': 'worker-construction-probe-manifest',
                'assignment_id': ASSIGNMENT, 'cases': cases}
    (HERE / 'context-probes-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    build()
