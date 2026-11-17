"""Proposed independent original-Native delivery audit for the red-curb pair.

Local operations must install this as state/operations/worker_exchange/delivery_audit.py.
Diagnostic fixtures exercise the row and review checkers only; no fixture can pass
the original-Native provenance gate in audit().
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from measure_red_curb import measure
from measure_exceptions import measure as measure_exception

ASSIGNMENT = 'training__C150142__LVMC-11-52-030-A__motor_vehicle_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
PIXEL_CLAIMS = {'ego_body', 'red_paint'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    require(path.is_file(), 'Missing delivery source: ' + str(path))
    return json.loads(path.read_text())


def lines(path):
    path = Path(path)
    require(path.is_file(), 'Missing delivery source: ' + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_rows(raw, frames, trace, map_readback, case, expected_frames,
                  source_kind='original_native', expected_red_stop=None):
    require(len(raw) == len(frames) == len(trace) == expected_frames and
            expected_frames >= 2, 'Original actor/frame/trace count differs')
    require(map_readback.get('source_kind') ==
            ('native_readback' if source_kind == 'original_native'
             else 'synthetic_native_sample') and
            map_readback.get('paint_color') == 'red',
            'Original red-paint readback missing')
    first = raw[0].get('native_frame')
    require(type(first) is int, 'Original Native frame identity absent')
    for index, (row, frame, point) in enumerate(zip(raw, frames, trace)):
        t = row.get('time_s')
        require(row.get('source_kind') == source_kind and
                row.get('frame') == index and
                row.get('native_frame') == first + index and
                frame.get('video_frame') == index and
                frame.get('native_frame') == first + index and
                frame.get('carla_frame') == first + index and
                point.get('frame') == first + index and
                finite(t) and finite(frame.get('time_s')) and
                finite(point.get('time_s')) and
                abs(frame['time_s'] - t) <= 1e-6 and
                abs(point['time_s'] - t) <= 1e-6 and
                set(frame.get('views', [])) == set(VIEWS),
                'Original actor/frame/trace join differs at ' + str(index))
        if index:
            require(0 < t - raw[index - 1]['time_s'] <= 0.051,
                    'Original 20 Hz source interval incomplete')
        require(isinstance(row.get('ego_body_native_xy_m'), list) and
                len(row['ego_body_native_xy_m']) >= 4 and
                isinstance(row.get('velocity_native_xyz_mps'), list) and
                len(row['velocity_native_xyz_mps']) == 3 and
                all(finite(v) for v in row['velocity_native_xyz_mps']),
                'Original ego body or velocity missing')
    curb = {'paint_color': map_readback['paint_color'],
            'source_kind': map_readback['source_kind'],
            'start_x_m': map_readback.get('red_curb_start_x_m'),
            'end_x_m': map_readback.get('red_curb_end_x_m'),
            'curb_y_m': map_readback.get('curb_y_m')}
    observation = measure(raw, frames, curb, expected_frames)
    expected = (case == ASSIGNMENT + '__reference' if expected_red_stop is None
                else expected_red_stop)
    require((case in (ASSIGNMENT + '__reference', ASSIGNMENT + '__contrast')
             if expected_red_stop is None else
             case.startswith(ASSIGNMENT + '__') and expected_red_stop is True) and
            observation['stopped_frame_ids'] and
            observation['red_curb_stop_or_park_observed'] is expected,
            'Original red-curb occupancy differs from exact case')
    return {'frames': expected_frames, 'native_frame_first': first,
            'native_frame_last': first + expected_frames - 1,
            'red_curb_stopped_frames': len(observation['red_curb_stopped_frame_ids']),
            'red_curb_stop_or_park_observed': expected}


def validate_review(review, case, candidate, attempt, primary,
                    extra_sources=(), required_claims=PIXEL_CLAIMS,
                    exception=False):
    require(review.get('source_kind') == 'original_native_review' and
            review.get('case_id') == case and
            review.get('candidate_id') == candidate and
            isinstance(review.get('reviewer_id'), str) and
            review['reviewer_id'].strip() and
            all(review.get(key) is True for key in
                ('painted_curb_visible', 'ego_body_visible',
                 'original_motion_reviewed', 'jurisdiction_and_signage_reviewed')) and
            review.get('legal_verdict') is None,
            'Independent original red-curb review incomplete')
    if exception:
        require(all(review.get(key) is True for key in
                    ('service_class_reviewed', 'activity_or_absence_reviewed',
                     'signage_readback_reviewed', 'mailbox_readback_reviewed')),
                'Independent original exception review incomplete')
    sources = review.get('sources', {})
    paths = {name: attempt / name for name in
             ('native-raw-actors.jsonl', 'native-map-readback.json',
              'video_frames.jsonl', 'trace.jsonl', 'config.json', 'result.json')}
    paths.update({name + '.mkv': attempt / (name + '.mkv') for name in VIEWS})
    paths['raw.mkv'] = primary
    paths.update({name: attempt / name for name in extra_sources})
    for name, path in paths.items():
        require(path.is_file() and sources.get(name) == sha(path),
                'Independent original review source hash differs: ' + name)
    boxes = review.get('pixel_boxes')
    require(isinstance(boxes, list) and
            {box.get('claim') for box in boxes} >= set(required_claims),
            'Independent review lacks red-paint/body pixel claims')
    return boxes


def validate_composition(receipt, attempt, primary, frames):
    require(receipt.get('format') == 'synchronized-four-view' and
            receipt.get('frames') == frames and
            receipt.get('frame_map_sha256') == sha(attempt / 'video_frames.jsonl') and
            receipt.get('primary_sha256') == sha(primary) and
            Path(receipt.get('primary', '')).resolve() == primary and
            all(receipt.get('sources', {}).get(name) ==
                sha(attempt / (name + '.mkv')) for name in VIEWS),
            'Composed four-view source binding differs')


def validate_exception_measurement(attempt, case_plan, case,
                                   source_kind='original_native'):
    """Recompute nonlegal exception facts from retained source rows."""
    attempt = Path(attempt)
    entries = [item for item in case_plan.get('cases', [])
               if item.get('case_id') == case and 'exception_spec' in item]
    require(len(entries) == 1, 'Unknown exact exception case')
    spec = entries[0]['exception_spec']
    config = read(attempt / 'config.json')
    report = read(attempt / 'analysis-report.json')
    result = read(attempt / 'result.json')
    map_readback = read(attempt / 'native-map-readback.json')
    raw = lines(attempt / 'native-raw-actors.jsonl')
    signed = report.get('measurements', {}).get('signed_curb_observation', {})
    value = signed.get('value', {})
    sources = signed.get('sources', {})
    require(config.get('case_id') == report.get('case_id') == case and
            result.get('case_id') == case and
            result.get('measured_values', {}).get('signed_curb_observation') ==
            {key: item for key, item in value.items() if key != 'legal_verdict'} and
            report.get('source_kind') == value.get('source_kind') == source_kind and
            map_readback.get('source_kind') ==
            ('native_readback' if source_kind == 'original_native'
             else 'synthetic_native_sample') and
            type(config.get('capture_frames', config.get('frames'))) is int and
            len(raw) == value.get('frames') ==
            config.get('capture_frames', config.get('frames')) and
            len(raw) >= 2 and
            config.get('service_class') == spec['service_class'] ==
            value.get('declared_service_class') and
            config.get('sign_classes') == spec['sign_classes'] ==
            value.get('displayed_sign_classes') and
            value.get('sign_present') is bool(spec['sign_classes']) and
            value.get('mailbox_present') is spec['mailbox_requested'],
            'Exception case, provenance or declared context differs')
    require(map_readback.get('sign_readback', {}).get('present') is
            value['sign_present'] and
            map_readback['sign_readback'].get('displayed_classes') ==
            value['displayed_sign_classes'] and
            map_readback.get('mailbox_readback', {}).get('present') is
            value['mailbox_present'],
            'Exception Native sign/mailbox readback differs')
    require({'native-raw-actors.jsonl', 'native-map-readback.json'} <= set(sources) and
            all(name.startswith('native-') and name.endswith(('.jsonl', '.json'))
                and '/' not in name and (attempt / name).is_file() and
                sources[name] == sha(attempt / name)
                for name in sources),
            'Exception measurement source hash differs')
    blueprints = {row.get('blueprint') for row in raw}
    require(blueprints == {config.get('native_blueprint')} and
            {row.get('source_kind') for row in raw} == {source_kind},
            'Exception Native vehicle identity/provenance differs')
    for name in sources:
        if name.endswith('-actors.jsonl') and name != 'native-raw-actors.jsonl':
            participant = lines(attempt / name)
            require(len(participant) == len(raw) and
                    all(row.get('source_kind') == source_kind and
                        row.get('frame') == index and
                        row.get('native_frame') == raw[index].get('native_frame') and
                        finite(row.get('time_s')) and
                        abs(row['time_s'] - raw[index]['time_s']) <= 1e-6
                        for index, row in enumerate(participant)),
                    'Exception participant Native frame join differs: ' + name)
    context = {'source_kind': source_kind,
               'red_curb': {'paint_color': map_readback.get('paint_color'),
                            'start_x_m': map_readback.get('red_curb_start_x_m'),
                            'end_x_m': map_readback.get('red_curb_end_x_m'),
                            'curb_y_m': map_readback.get('curb_y_m')},
               'sign_readback': map_readback['sign_readback'],
               'vehicle_readback': {'native_blueprint': config['native_blueprint'],
                                    'declared_service_class': config['service_class']},
               'mailbox_readback': map_readback['mailbox_readback']}
    computed = measure_exception(raw, context, [])
    require(abs(computed['red_curb_stationary_duration_s'] -
                value.get('red_curb_stationary_duration_s', -999)) <= 1e-6 and
            computed['duration_relative_to_30_minutes'] ==
            value.get('duration_relative_to_30_minutes'),
            'Exception measured stationary duration differs')
    events = value.get('recorded_activity_events')
    expected_activity = spec.get('activity_request')
    require(isinstance(events, list) and
            ({event.get('name') for event in events} ==
             ({expected_activity} if expected_activity else set())) and
            (not events or len(sources) > 2),
            'Exception activity lacks source-bound observation')
    return {'case_id': case, 'frames': len(raw),
            'stationary_duration_s': computed['red_curb_stationary_duration_s'],
            'duration_relative_to_30_minutes':
                computed['duration_relative_to_30_minutes'],
            'declared_service_class': config['service_class'],
            'recorded_activity_names': [event['name'] for event in events],
            'source_kind': source_kind, 'legal_verdict': None}


def pixel_checker(boxes, frames, required_claims=PIXEL_CLAIMS):
    by_frame = {}; seen = set(); identities = set()
    for box in boxes:
        index = box.get('frame'); rect = box.get('rect_xywh')
        require(type(index) is int and 0 <= index < frames and
                box.get('claim') in set(required_claims) and
                isinstance(rect, list) and len(rect) == 4 and
                all(type(v) is int for v in rect) and
                rect[2] >= 2 and rect[3] >= 2,
                'Invalid reviewed pixel box')
        identity = (index, tuple(rect))
        require(identity not in identities, 'Reviewed pixel claims reuse one box')
        identities.add(identity)
        by_frame.setdefault(index, []).append(box)

    def check(frame):
        for box in by_frame.get(frame.index, []):
            x, y, width, height = box['rect_xywh']
            require(0 <= x and 0 <= y and
                    x + width <= frame.width and y + height <= frame.height,
                    'Reviewed pixel box exceeds decoded video')
            values = []
            for row in range(y, y + height):
                offset = (row * frame.width + x) * 3
                values.extend(frame.pixels[offset:offset + width * 3])
            require(values and max(values) > min(values),
                    'Reviewed pixel box is flat')
            seen.add(box['claim'])
    return check, seen


def media_module():
    for parent in Path(__file__).resolve().parents:
        package = parent / 'runtime/pipeline/scenario_pipeline'
        if package.is_dir():
            sys.path.insert(0, str(package))
            from worker_exchange import media
            return media
    raise ValueError('Pinned media auditor unavailable')


def audit(case, job_id, attempt_number, recording_id, attempt, review_path,
          primary, decode_receipt, output):
    attempt = Path(attempt).resolve(); primary = Path(primary).resolve()
    output = Path(output).resolve(); decode_receipt = Path(decode_receipt).resolve()
    require(type(job_id) is int and job_id > 0 and
            type(attempt_number) is int and attempt_number > 0 and
            isinstance(recording_id, str) and recording_id and
            attempt.parent.name == recording_id and attempt in output.parents,
            'Canonical job, recording or attempt identity differs')
    require(not output.exists() and not decode_receipt.exists() and
            decode_receipt.parent != attempt and
            attempt in primary.parents and primary.is_file(),
            'Use fresh independent audit and operations-owned decode receipt')
    config = read(attempt / 'config.json')
    plan_path = attempt / 'case-plan.json'
    case_plan = read(plan_path)
    require(config.get('case_plan_sha256') == sha(plan_path),
            'Exact case-plan source hash differs')
    planned = [item for item in case_plan.get('cases', [])
               if item.get('case_id') == case]
    require(len(planned) == 1 and
            (case in (ASSIGNMENT + '__reference', ASSIGNMENT + '__contrast') or
             'exception_spec' in planned[0]), 'Wrong exact delivery case')
    exception = 'exception_spec' in planned[0]
    result = read(attempt / 'result.json')
    capture = read(attempt / 'native-capture-report.json')
    map_readback = read(attempt / 'native-map-readback.json')
    candidate = config.get('candidate_id')
    require(config.get('case_id') == result.get('case_id') ==
            capture.get('case_id') == case and
            candidate == capture.get('candidate_id') and
            result.get('accepted') is False and
            result.get('provenance_kind') == 'native' and
            capture.get('error') is None and
            capture.get('observed_frames') == config.get('frames'),
            'Original case, capture or result provenance differs')
    raw = lines(attempt / 'native-raw-actors.jsonl')
    frames = lines(attempt / 'video_frames.jsonl')
    trace = lines(attempt / 'trace.jsonl')
    physical = validate_rows(raw, frames, trace, map_readback, case,
                             config['frames'],
                             expected_red_stop=True if exception else None)
    extra_sources = set()
    claims = set(PIXEL_CLAIMS)
    if exception:
        physical['exception'] = validate_exception_measurement(
            attempt, case_plan, case)
        extra_sources.update(read(attempt / 'analysis-report.json')
                             ['measurements']['signed_curb_observation']['sources'])
        claims.add('service_vehicle')
        spec = planned[0]['exception_spec']
        if spec['sign_classes']:
            claims.add('sign_text')
        if spec['mailbox_requested']:
            claims.add('mailbox')
        if spec.get('activity_request'):
            claims.add('activity_actor')
    review = read(review_path)
    boxes = validate_review(review, case, candidate, attempt, primary,
                            extra_sources, claims, exception)
    media = media_module()
    media.check_four_view_sources({name: attempt / (name + '.mkv') for name in VIEWS})
    validate_composition(read(attempt / 'four-view-receipt.json'), attempt,
                         primary, config['frames'])
    checker, seen = pixel_checker(boxes, config['frames'], claims)
    media.audit(primary, config['frames'],
                checkers={'c150142_red_curb_pixels': (sha(Path(__file__)), checker)},
                mapping_sha256=sha(attempt / 'video_frames.jsonl'),
                receipt=decode_receipt)
    require(claims <= seen, 'Full decode omitted reviewed exception/body pixels')
    sources = {name: sha(attempt / name) for name in
               ('config.json', 'result.json', 'native-capture-report.json',
                'four-view-receipt.json',
                'native-raw-actors.jsonl', 'native-map-readback.json',
                'video_frames.jsonl', 'trace.jsonl')}
    sources.update({name + '.mkv': sha(attempt / (name + '.mkv')) for name in VIEWS})
    sources.update({name: sha(attempt / name) for name in extra_sources})
    sources['raw.mkv'] = sha(primary)
    core = attempt / 'converted/trace.json'
    require(core.is_file(), 'Missing converted trace')
    core_rows = read(core).get('scenes')
    require(isinstance(core_rows, list) and len(core_rows) == config['frames'] and
            all(scene.get('t') == round(frame['time_s'] * 1000)
                for scene, frame in zip(core_rows, frames)),
            'Converted trace and Native frame times differ')
    receipt = {'format': 'worker-delivery-audit', 'passed': True,
               'case_id': case, 'candidate_id': candidate, 'job_id': job_id,
               'attempt': attempt_number, 'recording_id': recording_id,
               'source_result_sha256': sources['result.json'],
               'frames': config['frames'], 'video': 'raw.mkv',
               'video_sha256': sources['raw.mkv'], 'trace': 'converted/trace.json',
               'trace_sha256': sha(core), 'frame_map_sha256': sources['video_frames.jsonl'],
               'checks': {name: True for name in CHECKS}, 'sources': sources,
               'physical_observation': physical, 'review_sha256': sha(review_path),
               'auditor_path': str(Path(__file__).resolve()),
               'auditor_sha256': sha(Path(__file__)),
               'source_decode_receipt_path': str(decode_receipt),
               'source_decode_receipt_sha256': sha(decode_receipt),
               'source_decode_auditor_sha256': sha(Path(media.__file__)),
               'legal_verdict': None}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    for name in ('case', 'job_id', 'attempt_number', 'recording_id', 'attempt',
                 'review', 'primary', 'decode_receipt', 'output'):
        parser.add_argument('--' + name.replace('_', '-'), required=True,
                            type=int if name in ('job_id', 'attempt_number') else str)
    args = parser.parse_args()
    result = audit(args.case, args.job_id, args.attempt_number,
                   args.recording_id, args.attempt, args.review,
                   args.primary, args.decode_receipt, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
