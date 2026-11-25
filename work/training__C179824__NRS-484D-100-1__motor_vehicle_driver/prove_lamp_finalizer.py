"""Recorded-only finalizer proof with explicit synthetic provenance."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from finalize_lamp import REVIEW_SOURCES, finalize
from prove_lamp_saved_measure import sample


def raw(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def rows(items):
    return b''.join(raw(item) for item in items)


def attempt(root, suffix, omit=None):
    case = 'training__C179824__NRS-484D-100-1__motor_vehicle_driver__' + suffix
    packet, context = sample(lamps_on=suffix == 'controlled_1')
    for row in packet['frames']:
        row['vehicle_xy_m'] = [-70 + row['video_frame'] * 0.15, -1.75]
    road = b'<OpenDRIVE diagnostic="synthetic-shape-only" />'
    context['map_source_sha256'] = hashlib.sha256(road).hexdigest()
    for field in ('highway_source_sha256','vehicle_class_source_sha256',
                  'device_content_source_sha256','device_authority_source_sha256',
                  'device_placement_source_sha256','device_timing_source_sha256',
                  'public_highway','vehicle_class','device_official'):
        context[field] = None
    config = {'case_id':case, 'supported_case_ids':[case],
              'recording_description': {'channels':[
                  {'name':'native_lamp_setting','unit':'boolean','sampling_rate_hz':20,
                   'method':'original light-state readback','time_window':'600 frames',
                   'reference_frame':'governed roadway','uncertainty':'pixels unverified'}]}}
    (root / 'config.json').write_bytes(raw(config))
    (root / 'road.xodr').write_bytes(road)
    (root / 'vehicle-lamps.jsonl').write_bytes(rows(packet['frames']))
    mapping = [{'video_frame':f['video_frame'], 'native_frame':f['native_frame'],
                'carla_frame':f['native_frame'],
                'time_s':f['time_s'], 'camera_native_frames':f['camera_native_frames']}
               for f in packet['frames']]
    (root / 'video_frames.jsonl').write_bytes(rows(mapping))
    original_context_raw = raw(context)
    (root / 'lamp-context.json').write_bytes(original_context_raw)
    review_packet = {'case_id':case, 'review_kind':'synthetic_diagnostic',
                     'original_context_sha256':hashlib.sha256(original_context_raw).hexdigest(),
                     'state':'Nevada','public_highway':True,
                     'vehicle_class':'ordinary_motor_vehicle',
                     'directive':'use_lamps','device_official':True,
                     'device_governs_road_id':'1'}
    for field, name in REVIEW_SOURCES.items():
        review = {'case_id':case, 'review_kind':'synthetic_diagnostic',
                  'field':field,'source_note':'synthetic source shape only'}
        content = raw(review)
        review_packet[field] = hashlib.sha256(content).hexdigest()
        if name != omit:
            (root / name).write_bytes(content)
    (root / 'lamp-source-review.json').write_bytes(raw(review_packet))
    return case


def main():
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import validate_result
    scratch = repo / '.runtime-work' / 'c179824'
    scratch.mkdir(parents=True, exist_ok=True)
    positives = []
    negatives = []
    for suffix in ('controlled_1','controlled_2'):
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            case = attempt(root, suffix)
            report = finalize(root, root / 'analysis.json')
            result = json.loads((root / 'result.json').read_text())
            validate_result(result)
            if report['case_id'] != case or result['case_id'] != case or not result['target_checks'][0]['matched']:
                raise AssertionError('selected lamp case failed: ' + suffix)
            if result['accepted'] or report['legal_verdict_claimed']:
                raise AssertionError('synthetic diagnostic asserted acceptance')
            positives.append(suffix)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            missing = 'device-authority-review.json'
            attempt(root, suffix, omit=missing)
            try:
                finalize(root, root / 'analysis.json')
            except ValueError as exc:
                if str(exc) != 'Missing required source: ' + missing:
                    raise
            else:
                raise AssertionError('missing authority review accepted')
            negatives.append(suffix + '_missing_authority')
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            attempt(root, suffix)
            context = json.loads((root / 'lamp-context.json').read_text())
            context['road_id'] = '2'
            (root / 'lamp-context.json').write_bytes(raw(context))
            try:
                finalize(root, root / 'analysis.json')
            except ValueError as exc:
                if str(exc) != 'independent review does not bind original context':
                    raise
            else:
                raise AssertionError('changed original context accepted')
            negatives.append(suffix + '_changed_original_context')
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            attempt(root, suffix)
            context = json.loads((root / 'lamp-context.json').read_text())
            context['source_kind'] = 'native_saved_sample'
            (root / 'lamp-context.json').write_bytes(raw(context))
            review_packet = json.loads((root / 'lamp-source-review.json').read_text())
            review_packet['original_context_sha256'] = hashlib.sha256(raw(context)).hexdigest()
            review_packet['review_kind'] = 'original_source_review'
            for field, name in REVIEW_SOURCES.items():
                review = json.loads((root / name).read_text())
                review['review_kind'] = 'original_source_review'
                content = raw(review)
                (root / name).write_bytes(content)
                review_packet[field] = hashlib.sha256(content).hexdigest()
            (root / 'lamp-source-review.json').write_bytes(raw(review_packet))
            try:
                finalize(root, root / 'analysis.json')
            except ValueError as exc:
                if str(exc) != 'Missing original camera video: overview':
                    raise
            else:
                raise AssertionError('original claim without camera video accepted')
            negatives.append(suffix + '_missing_original_video')
    print(json.dumps({'passed':True,'positive_cases':positives,
                      'negative_checks':negatives,
                      'recorded_only':True,'synthetic_only':True,
                      'physical_or_legal_acceptance_claimed':False},sort_keys=True))


if __name__ == '__main__':
    main()
