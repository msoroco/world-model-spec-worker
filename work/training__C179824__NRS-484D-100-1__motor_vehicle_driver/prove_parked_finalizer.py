"""Exercise parked finalizer on a labeled synthetic source and missing-source negative."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT/'.runtime-work/c179824'
SOURCES = ('visibility-trace.jsonl', 'video_frames.jsonl', 'road.xodr',
           'visibility-context.json', 'visibility-pixel-review.json',
           'civil-clock.json', 'civil-time-review.json', 'sun-event-source.json',
           'location-source.json', 'vehicle-lamps.jsonl', 'lamp-context.json',
           'lamp-source-review.json', 'highway-review.json',
           'vehicle-class-review.json', 'device-content-review.json',
           'device-authority-review.json', 'device-placement-review.json',
           'device-timing-review.json', 'overview.mkv', 'approach.mkv',
           'reference_corner.mkv', 'driver_reference.mkv')
REVIEWS = {'highway_source_sha256': 'highway-review.json',
           'vehicle_class_source_sha256': 'vehicle-class-review.json',
           'device_content_source_sha256': 'device-content-review.json',
           'device_authority_source_sha256': 'device-authority-review.json',
           'device_placement_source_sha256': 'device-placement-review.json',
           'device_timing_source_sha256': 'device-timing-review.json'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def fixture(suffix):
    case_id = HERE.name+'__'+suffix
    reference = SCRATCH/('full-device-'+suffix[-1]+'-primary-compat-v2')
    output = SCRATCH/'parked-finalizer-fixture'/suffix
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in SOURCES:
        src = reference/name
        dst = output/name
        if name.endswith('.mkv'):
            os.link(src, dst)
        else:
            shutil.copy2(src, dst)
    offline = SCRATCH/('parked-offline-'+suffix[-1]+'-primary')
    shutil.copy2(offline/'config.json', output/'config.json')
    lamp_rows = [json.loads(line) for line in (output/'vehicle-lamps.jsonl').read_text().splitlines()]
    visibility_rows = [json.loads(line) for line in (output/'visibility-trace.jsonl').read_text().splitlines()]
    parked_rows = []
    for i, (lamp, visibility) in enumerate(zip(lamp_rows, visibility_rows)):
        if i >= 500:
            lamp['speed_mps'] = 0.0
            visibility['ego_speed_mps'] = 0.0
            visibility['ego_xy_m'][1] = -4.75
        parked_rows.append({'source_kind': 'synthetic_diagnostic',
                            'video_frame': i, 'native_frame': lamp['native_frame'],
                            'time_s': lamp['time_s'], 'speed_mps': lamp['speed_mps'],
                            'road_id': lamp['road_id'],
                            'camera_native_frames': lamp['camera_native_frames'],
                            'on_shoulder_readback': i >= 500})
    for name, rows in (('vehicle-lamps.jsonl', lamp_rows),
                       ('visibility-trace.jsonl', visibility_rows),
                       ('parked-trace.jsonl', parked_rows)):
        (output/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
    pixel_review = json.loads((output/'visibility-pixel-review.json').read_text())
    pixel_review['trace_sha256'] = sha(output/'visibility-trace.jsonl')
    dump(output/'visibility-pixel-review.json', pixel_review)
    for name in REVIEWS.values():
        value = json.loads((output/name).read_text())
        value['case_id'] = case_id
        dump(output/name, value)
    review = json.loads((output/'lamp-source-review.json').read_text())
    review['case_id'] = case_id
    for field, name in REVIEWS.items():
        review[field] = sha(output/name)
    dump(output/'lamp-source-review.json', review)
    for name in ('nrs-484d-165-source.json', 'parked-highway-review.json',
                 'parked-status-review.json'):
        dump(output/name, {'case_id': case_id, 'source_kind': 'synthetic_diagnostic',
                           'original_source_reviewed': False})
    parked_review = {'source_kind': 'synthetic_diagnostic',
                     'trace_sha256': sha(output/'parked-trace.jsonl'),
                     'reviewer_id': 'cpu-diagnostic-only',
                     'highway_and_shoulder_source_sha256': sha(output/'parked-highway-review.json'),
                     'parked_status_source_sha256': sha(output/'parked-status-review.json'),
                     'nrs_484d_165_source_sha256': sha(output/'nrs-484d-165-source.json'),
                     'pixel_video_name': 'driver_reference.mkv',
                     'pixel_video_sha256': sha(output/'driver_reference.mkv'),
                     'on_traveled_portion_or_adjacent_shoulder': True,
                     'insufficient_light_at_1000ft': True,
                     'front_lamp_visible_at_500ft': True,
                     'rear_lamp_visible_at_500ft': True,
                     'lamp_near_traffic_side': True,
                     'headlamp_dimmed_if_lit': True,
                     'original_source_reviewed': False}
    dump(output/'parked-exception-review.json', parked_review)
    return output


def run(suffix, negative=False):
    attempt = fixture(suffix)
    if negative:
        (attempt/'parked-status-review.json').unlink()
    command = [str(ROOT/'.venv-cpu/bin/python'), '-B',
               str(SCRATCH/('parked-offline-'+suffix[-1]+'-primary')/'finalize_parked.py'),
               '--attempt', str(attempt), '--output', str(attempt/'analysis-report.json')]
    environment = os.environ.copy()
    environment['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH)
    environment['TMPDIR'] = str(SCRATCH)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['PYTHONPATH'] = str(ROOT/'runtime/scenario_pipeline')
    result = subprocess.run(command, cwd=ROOT, env=environment,
                            capture_output=True, text=True)
    expected = 1 if negative else 0
    if (result.returncode == 0) != (expected == 0):
        raise RuntimeError('parked finalizer proof gave unexpected exit: '+result.stderr[-500:])
    if negative and 'Missing required source: parked-status-review.json' not in result.stderr:
        raise RuntimeError('missing parked source negative did not fail at source gate')
    if not negative:
        analysis = json.loads((attempt/'analysis-report.json').read_text())
        value = analysis['measurements']['lamp_device_measurement']['value']
        assert value['parked_exception']['parked_final_frames'] == 100
        assert not analysis['legal_verdict_claimed']
    return {'case_id': HERE.name+'__'+suffix, 'negative': negative,
            'passed': True, 'synthetic_diagnostic': True,
            'original_native_observed': False}


def main():
    rows = [run(suffix) for suffix in ('parked_lamps_1', 'parked_lamps_2')]
    rows.append(run('parked_lamps_1', negative=True))
    print(json.dumps({'format': 'c179824-parked-finalizer-cpu-proof-v1',
                      'checks': rows, 'all_passed': True,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
