"""Synthetic route topology/purpose variants and negative source checks."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_through_route import AID, CAMERAS, COUNT, measure
from measure_purpose_route import measure_purpose


def save(path, rows):
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def reject(root, changed, mutation):
    path = root/changed
    original = path.read_bytes()
    try:
        if changed.endswith('.jsonl'):
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            if mutation == 'frame':
                rows[200]['native_frame'] = rows[199]['native_frame']
            elif mutation == 'provenance':
                rows[200]['source_kind'] = 'original_native_pose'
            elif mutation == 'actor':
                rows[200]['ego_actor_id'] = 99
            elif mutation == 'jump':
                rows[200]['ego_x_m'] += 20
            save(path, rows)
        else:
            context = json.loads(path.read_text())
            if mutation == 'camera_hash':
                context['camera_sha256'] = {}
            elif mutation == 'designation':
                del context['truck_route_designation_source']
            elif mutation == 'purpose':
                context['enroute_purpose'] = 'guessed_from_stop'
            elif mutation == 'route_ids':
                context['exit_truck_route_id'] = 100
            path.write_text(json.dumps(context)+'\n')
        try:
            measure(root)
        except ValueError as exc:
            return {'mutation': mutation, 'rejected': str(exc)}
        raise AssertionError('Mutation accepted: '+mutation)
    finally:
        path.write_bytes(original)


def main():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        for name in CAMERAS:
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=64x48:r=20',
                            '-frames:v', str(COUNT), '-c:v', 'ffv1', str(root/(name+'.mkv'))], check=True)
        hashes = {(name+'.mkv'): hashlib.sha256((root/(name+'.mkv')).read_bytes()).hexdigest()
                  for name in CAMERAS}
        frames = [{'video_frame': i, 'native_frame': 1000+i, 'time_s': round(i*.05, 4)} for i in range(COUNT)]
        save(root/'video_frames.jsonl', frames)
        context = {'assignment_id': AID, 'case_id': AID+'__probe_01',
                   'review_kind': 'synthetic_diagnostic', 'reviewer': 'synthetic-software-test',
                   'camera_sha256': hashes, 'truck_blueprint_source': 'synthetic fixture',
                   'truck_route_designation_source': 'synthetic fixture',
                   'nontruck_street_designation_source': 'synthetic fixture',
                   'route_connectivity_source': 'synthetic fixture',
                   'enroute_purpose_source': 'synthetic fixture', 'served_premises_source': 'synthetic fixture',
                   'entry_truck_route_id': 100, 'intervening_street_id': 200,
                   'exit_truck_route_id': 300, 'ego_actor_id': 7, 'vehicle_is_truck': True,
                   'enroute_purpose': 'none'}
        variants = []
        for label, purpose, ids in (
                ('through_no_purpose', 'none', (100, 200, 300)),
                ('through_delivery', 'delivery', (100, 200, 300)),
                ('incomplete_trip', 'none', (100, 200, 200)),
                ('direct_truck_routes', 'none', (100, 300, 300))):
            context['enroute_purpose'] = purpose
            (root/'route_context.json').write_text(json.dumps(context)+'\n')
            trace = [{'video_frame': i, 'native_frame': 1000+i, 'source_kind': 'synthetic_native_sample',
                      'ego_actor_id': 7, 'road_id': ids[0 if i < 150 else 1 if i < 450 else 2],
                      'ego_x_m': round(i*.1, 4), 'ego_y_m': 0.0, 'ego_speed_mps': 2.0} for i in range(COUNT)]
            save(root/'native_route_trace.jsonl', trace)
            observed = measure(root)
            assert observed['complete_truck_to_truck_passage'] == (label.startswith('through_'))
            assert observed['enroute_purpose_reviewed'] == purpose
            assert observed['purpose_inferred_from_stop'] is False
            variants.append({'name': label, 'road_sequence': observed['observed_road_sequence'],
                             'complete': observed['complete_truck_to_truck_passage'], 'purpose': purpose})
        context['enroute_purpose'] = 'delivery'
        context['case_id'] = AID+'__probe_02'
        context['service_stop_complete'] = True
        (root/'route_context.json').write_text(json.dumps(context)+'\n')
        trace = [{'video_frame': i, 'native_frame': 1000+i, 'source_kind': 'synthetic_native_sample',
                  'ego_actor_id': 7, 'road_id': 100 if i < 150 else 200 if i < 450 else 300,
                  'ego_x_m': round((i if i < 220 else 220 if i < 320 else i-100)*.1, 4), 'ego_y_m': 0.0,
                  'ego_speed_mps': 0.0 if 220 <= i < 320 else 2.0,
                  'service_stop_active': 220 <= i < 320} for i in range(COUNT)]
        save(root/'native_route_trace.jsonl', trace)
        purpose_observed = measure_purpose(root)
        assert purpose_observed['reviewed_service_stop_frames'] == 100
        context['service_stop_complete'] = False
        (root/'route_context.json').write_text(json.dumps(context)+'\n')
        try:
            measure_purpose(root)
        except ValueError as exc:
            assert 'Missing 100-frame original stop' in str(exc)
            purpose_negative = str(exc)
        else:
            raise AssertionError('Unfinished service stop accepted')
        context['service_stop_complete'] = True
        (root/'route_context.json').write_text(json.dumps(context)+'\n')
        trace[250]['service_stop_active'] = False
        save(root/'native_route_trace.jsonl', trace)
        try:
            measure_purpose(root)
        except ValueError as exc:
            assert 'Missing 100-frame original stop' in str(exc)
            interrupted_stop_negative = str(exc)
        else:
            raise AssertionError('Interrupted service stop accepted')
        trace[250]['service_stop_active'] = True
        save(root/'native_route_trace.jsonl', trace)
        negatives = [reject(root, 'native_route_trace.jsonl', 'frame'),
                     reject(root, 'native_route_trace.jsonl', 'provenance'),
                     reject(root, 'native_route_trace.jsonl', 'actor'),
                     reject(root, 'native_route_trace.jsonl', 'jump'),
                     reject(root, 'route_context.json', 'camera_hash'),
                     reject(root, 'route_context.json', 'designation'),
                     reject(root, 'route_context.json', 'purpose'),
                     reject(root, 'route_context.json', 'route_ids')]
        print(json.dumps({'assignment_id': AID, 'software_proof': 'synthetic_diagnostic',
                          'variants': variants, 'negative_rejections': negatives,
                          'purpose_stop_positive_frames': purpose_observed['reviewed_service_stop_frames'],
                          'purpose_stop_negative_rejections': [purpose_negative, interrupted_stop_negative],
                          'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
