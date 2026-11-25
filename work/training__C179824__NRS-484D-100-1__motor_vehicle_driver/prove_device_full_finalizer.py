"""CPU source-shape proof for full-law device pair finalization."""
import hashlib
import json
from pathlib import Path
import tempfile

from native.finalize_full_lamp import REVIEW_SOURCES, finalize
from prove_boundary_saved import synthetic_packet


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(root, suffix, missing=None):
    case_id = HERE.name+'__'+suffix
    raw = synthetic_packet()
    trace = [json.loads(line) for line in raw['visibility-trace.jsonl'].splitlines() if line]
    lamp_rows = []
    lamp_on = suffix == 'controlled_1'
    for item in trace:
        index = item['video_frame']
        lamp_rows.append({'video_frame': index, 'native_frame': item['native_frame'],
                          'time_s': item['time_s'], 'vehicle_id': '107',
                          'vehicle_blueprint_id': 'vehicle.tesla.model3',
                          'road_id': '1', 'vehicle_xy_m': item['ego_xy_m'],
                          'speed_mps': item['ego_speed_mps'],
                          'device_active': index >= 100,
                          'headlamp_setting_on': lamp_on,
                          'position_lamp_setting_on': lamp_on,
                          'native_light_state_bits': 3 if lamp_on else 0,
                          'camera_native_frames': item['camera_native_frames']})
    raw['vehicle-lamps.jsonl'] = b''.join(enc(row) for row in lamp_rows)
    original_lamp = {
        'assignment_id': HERE.name, 'source_kind': 'synthetic_diagnostic',
        'road_id': '1', 'map_source_sha256': sha(raw['road.xodr']),
        'state': 'Nevada', 'public_highway': None, 'vehicle_class': None,
        'directive': 'use_lamps', 'device_official': None,
        'device_governs_road_id': '1'}
    raw['lamp-context.json'] = enc(original_lamp)
    review = {'case_id': case_id, 'review_kind': 'synthetic_diagnostic',
              'original_context_sha256': sha(raw['lamp-context.json']),
              'state': 'Nevada', 'public_highway': True,
              'vehicle_class': 'ordinary_motor_vehicle',
              'directive': 'use_lamps', 'device_official': True,
              'device_governs_road_id': '1'}
    for field, name in REVIEW_SOURCES.items():
        raw[name] = enc({'case_id': case_id, 'review_kind': 'synthetic_diagnostic',
                         'source_note': 'CPU source-shape fixture'})
        review[field] = sha(raw[name])
    raw['lamp-source-review.json'] = enc(review)
    for name, content in raw.items():
        if name != missing:
            (root/name).write_bytes(content)
    recording = json.loads((HERE/'proposals/boundary-cases-draft.json').read_text())['cases'][0]['recording_description']
    config = {'case_id': case_id, 'lamp_setting_on': lamp_on,
              'boundary_request': {'target_distance_ft': 1000,
                                   'civil_branch': None, 'civil_offset_min': None},
              'recording_description': recording}
    (root/'config.json').write_bytes(enc(config))
    return case_id


def main():
    scratch = ROOT/'.runtime-work/c179824'
    scratch.mkdir(parents=True, exist_ok=True)
    positives = []
    for suffix in ('controlled_1', 'controlled_2'):
        with tempfile.TemporaryDirectory(dir=scratch, prefix='device-full-') as tmp:
            root = Path(tmp)
            case = prepare(root, suffix)
            report = finalize(root, root/'analysis-report.json')
            from worker_exchange.native_output import validate_result
            result = validate_result(json.loads((root/'result.json').read_text()))
            if (report['case_id'] != case or result['case_id'] != case or
                    not result['target_checks'][0]['matched']):
                raise AssertionError('source-bound device pair failed')
            if (result['accepted'] or result['legal_verdict_claimed'] or
                    not result['diagnostic_fixture']):
                raise AssertionError('diagnostic provenance changed')
            positives.append(suffix)
        with tempfile.TemporaryDirectory(dir=scratch, prefix='device-full-negative-') as tmp:
            root = Path(tmp)
            prepare(root, suffix, missing='device-authority-review.json')
            try:
                finalize(root, root/'analysis-report.json')
            except ValueError as error:
                if str(error) != 'Missing required source: device-authority-review.json':
                    raise
            else:
                raise AssertionError('missing official authority source accepted')
    print(json.dumps({'passed': True, 'positive_cases': positives,
                      'missing_authority_negatives': 2,
                      'diagnostic_fixture': True,
                      'original_capture_attested': False}, sort_keys=True))


if __name__ == '__main__':
    main()
