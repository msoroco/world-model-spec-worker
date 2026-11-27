"""Finalize original taxi/light-express sources without deciding eligibility."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from freight_plan import VIEWS, check_request, measure_saved

SOURCES = ('freight-native.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'road.xodr', 'yellow-freight-road.xodr',
           'sign-authority-pending.json', 'commercial-status-review.json',
           'sign-review.json', 'freight-purpose-review.json',
           *(name + '.mkv' for name in VIEWS))


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def source_measurement(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / 'config.json').read_text())
    check_request(config, (attempt / 'yellow-freight-road.xodr').read_text())
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    seal = attempt / 'capture-seal.json'
    kind = 'original_native' if seal.is_file() else 'synthetic_cpu_fixture'
    if kind == 'synthetic_cpu_fixture':
        recorder = attempt / 'capture' / 'recorder_info.txt'
        if not recorder.is_file() or 'Synthetic' not in recorder.read_text():
            raise ValueError('Unsealed freight acquisition is not a diagnostic')
    manifest = attempt / 'source-manifest.json'
    if kind == 'original_native':
        if not manifest.is_file():
            raise ValueError('Missing original freight source manifest')
        source_index = json.loads(manifest.read_text())
        if source_index.get('capture_seal_sha256') != sha(seal):
            raise ValueError('Freight capture seal not bound')
    else:
        if manifest.exists():
            raise ValueError('Unsealed freight source manifest already exists')
        source_index = {'source_kind': kind,
                        'sha256': {name: sha(attempt / name) for name in SOURCES}}
        manifest.write_text(json.dumps(source_index, indent=2) + '\n')
    if source_index.get('source_kind') != kind or set(source_index.get('sha256', {})) != set(SOURCES):
        raise ValueError('Exact freight source inventory differs')
    if any(source_index['sha256'][name] != sha(attempt / name) for name in SOURCES):
        raise ValueError('Freight source changed after inventory')
    commercial = json.loads((attempt / 'commercial-status-review.json').read_text())
    sign = json.loads((attempt / 'sign-review.json').read_text())
    purpose = json.loads((attempt / 'freight-purpose-review.json').read_text())
    review_rows = (('commercial-status-review.json', commercial,
                    {'freight-native.jsonl', 'overview.mkv'}),
                   ('sign-review.json', sign,
                    {'yellow-freight-road.xodr', 'reference_corner.mkv'}),
                   ('freight-purpose-review.json', purpose,
                    {'freight-native.jsonl', 'approach.mkv'}))
    for name, review, required_refs in review_rows:
        if (review.get('source_kind') != kind or not review.get('source_basis') or
                review.get('legal_verdict') is not None):
            raise ValueError('Independent freight review missing: ' + name)
        if kind == 'synthetic_cpu_fixture' and review.get('synthetic_cpu_fixture') is not True:
            raise ValueError('Fixture review provenance missing: ' + name)
        if kind == 'original_native':
            refs = review.get('source_refs')
            if not isinstance(refs, dict) or not required_refs <= set(refs):
                raise ValueError('Original freight review has no source binding: ' + name)
            for rel, digest in refs.items():
                if rel not in source_index['sha256'] or digest != source_index['sha256'][rel]:
                    raise ValueError('Original freight review source binding differs: ' + name)
    if (purpose.get('observed_purpose') != config['requested_purpose'] or
            sign.get('observed_curb_color') != 'yellow' or
            sign.get('posted_hours_start') != '09:00' or
            sign.get('posted_hours_end') != '17:00' or
            not sign.get('observed_sign_content') or
            'observed_commercial_use' not in commercial):
        raise ValueError('Freight purpose, curb or posted condition differs')
    native, frame_map, trace = (rows(attempt / name) for name in
                                ('freight-native.jsonl', 'video_frames.jsonl', 'trace.jsonl'))
    if not all(len(items) == 600 for items in (native, frame_map, trace)):
        raise ValueError('Full 600-frame freight Native join required')
    for i, (n, f, t) in enumerate(zip(native, frame_map, trace)):
        frame = n.get('native_frame')
        expected_time = (i + 1) / 20
        cameras = f.get('camera_native_frames')
        if (not isinstance(frame, int) or f.get('video_frame') != i or
                f.get('carla_frame') != frame or t.get('frame') != frame or
                n.get('source_kind') != kind or t.get('source_kind') != kind or
                not all(math.isclose(row.get('time_s', -1), expected_time, abs_tol=1e-4)
                        for row in (n, f, t)) or
                not isinstance(cameras, dict) or set(cameras) != set(VIEWS) or
                any(value != frame for value in cameras.values()) or
                n.get('source_cameras') != cameras):
            raise ValueError('Freight original frame/time/four-view join differs')
    measured = measure_saved(native, config)
    measured['observed_purpose'] = purpose['observed_purpose']
    if (commercial.get('taxi_actor_id') != native[0]['taxi_actor_id'] or
            type(commercial.get('observed_taxicab')) is not bool or
            purpose.get('cargo_actor_id') != native[0]['cargo_actor_id']):
        raise ValueError('Freight identity review differs from original Native actors')
    measured['source_manifest_sha256'] = sha(manifest)
    measured['original_native_observed'] = kind == 'original_native'
    measured['commercial_review_source'] = commercial['source_basis']
    measured['sign_review_source'] = sign['source_basis']
    measured['freight_purpose_review_source'] = purpose['source_basis']
    return measured


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Fresh freight saved analysis required')
    config = json.loads((attempt / 'config.json').read_text())
    measured = source_measurement(attempt)
    if measured['case_id'] != config['case_id']:
        raise ValueError('Freight case identity differs')
    construction = json.loads((attempt / 'construction.json').read_text())
    if construction.get('case_id') != config['case_id']:
        raise ValueError('Freight construction identity differs')
    channels = construction['recording_description']['channels']
    commercial = json.loads((attempt / 'commercial-status-review.json').read_text())
    sign = json.loads((attempt / 'sign-review.json').read_text())
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=False)
    native = rows(attempt / 'freight-native.jsonl')
    for channel in channels:
        name = channel['name']
        with (channel_dir / (name + '.jsonl')).open('x') as stream:
            for row in native:
                value = (row['civil_time_local'] if name == 'env.civil_time'
                         else row['time_s'] if name == 'kin.time'
                         else row['taxi_velocity_xyz_mps'] if name == 'drv.standing_or_parked'
                         else row['cargo_transfer_motion_observed'] if name == 'sig.door_open'
                         else 0 if name == 'ru.occupant_count'
                         else {'actor_id': commercial['taxi_actor_id'],
                               'classification_review': commercial.get('observed_commercial_use'),
                               'source_basis': commercial['source_basis']}
                              if name == 'ru.commercial_motor_vehicle'
                         else sign.get('observed_sign_content') if name == 'dev.regulatory_sign'
                         else commercial['observed_taxicab'] if name == 'ru.taxicab'
                         else ('09:00' <= row['civil_time_local'][11:16] < '17:00')
                              if name == 'drv.condition_in_effect'
                         else 'yellow')
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
    sources = {name: sha(attempt / name) for name in SOURCES}
    report = {'format': 'worker-analysis-report', 'case_id': config['case_id'],
              'measurements': {'freight_yellow_zone_measurement': {
                  'method': 'source_measurement', 'value': measured, 'sources': sources}},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    result = {'case_id': config['case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'observed cargo transfer motion',
                  'requested': config['requested_purpose'],
                  'measured': measured['cargo_transfer_motion_frames'],
                  'method': 'source_measurement', 'tolerance': None,
                  'matched': False, 'physical_cause_confirmed': False,
                  'cause_evidence': list(sources)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved freight source measurement; physical and legal review pending',
              'physical_failure_flags': ['Commercial and freight classification unconfirmed'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': [{'name': c['name'], 'unit': c['unit'],
                                      'reference': 'channels/' + c['name'] + '.jsonl'}
                                     for c in channels],
              'realized_observables': {},
              'provenance_kind': 'original_source_review' if measured['original_native_observed']
                                 else 'synthetic_local_diagnostic',
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
