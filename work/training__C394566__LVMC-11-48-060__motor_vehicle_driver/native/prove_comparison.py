"""Synthetic source-joined comparison positive and independent negative checks."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from comparison_audit import audit
from measure_through_route import AID, CAMERAS, COUNT


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True)+'\n')


def lines(path, value):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in value))


def reject(first, second, path, changed, expected):
    original = path.read_bytes()
    try:
        changed(path)
        try:
            audit(first, second)
        except (ValueError, FileNotFoundError) as exc:
            if expected not in str(exc):
                raise AssertionError('Wrong comparison rejection: '+str(exc))
            return str(exc)
        raise AssertionError('Invalid comparison was accepted')
    finally:
        path.write_bytes(original)


def main():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        first, second = Path(tmp)/'first', Path(tmp)/'second'
        first.mkdir(); second.mkdir()
        for name in CAMERAS:
            path = first/(name+'.mkv')
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'color=c=black:s=64x48:r=20',
                            '-frames:v', str(COUNT), '-an', '-c:v', 'ffv1',
                            '-threads', '1', '-fflags', '+bitexact', '-flags:v', '+bitexact',
                            str(path)], check=True)
            os.link(path, second/path.name)
        hashes = {(name+'.mkv'): hashlib.sha256((first/(name+'.mkv')).read_bytes()).hexdigest()
                  for name in CAMERAS}
        frames = [{'video_frame': i, 'native_frame': 1000+i, 'time_s': round(i*.05, 4)}
                  for i in range(COUNT)]
        for root in (first, second):
            lines(root/'video_frames.jsonl', frames)
        context = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic',
                   'reviewer': 'synthetic-software-test', 'camera_sha256': hashes,
                   'truck_blueprint_source': 'synthetic common truck blueprint',
                   'truck_route_designation_source': 'synthetic common designation',
                   'nontruck_street_designation_source': 'synthetic common designation',
                   'route_connectivity_source': 'synthetic common route',
                   'enroute_purpose_source': 'synthetic reviewed purpose',
                   'served_premises_source': 'synthetic reviewed premises',
                   'entry_truck_route_id': 100, 'intervening_street_id': 200,
                   'exit_truck_route_id': 300, 'ego_actor_id': 7,
                   'vehicle_is_truck': True}
        one = dict(context, case_id=AID+'__probe_01', enroute_purpose='none')
        two = dict(context, case_id=AID+'__probe_02', enroute_purpose='delivery',
                   service_stop_complete=True, service_stop_frames=100)
        save(first/'route_context.json', one)
        save(second/'route_context.json', two)
        for root, stop in ((first, False), (second, True)):
            trace = []
            for i in range(COUNT):
                x = (i*.1 if not stop else
                     (i if i < 220 else 220 if i < 320 else i-100)*.12)
                road = 100 if x < 15 else 200 if x < 45 else 300
                trace.append({'video_frame': i, 'native_frame': 1000+i,
                              'source_kind': 'synthetic_native_sample', 'ego_actor_id': 7,
                              'road_id': road, 'ego_x_m': round(x, 4), 'ego_y_m': 0.0,
                              'ego_speed_mps': 0.0 if stop and 220 <= i < 320 else 2.4 if stop else 2.0,
                              'service_stop_active': bool(stop and 220 <= i < 320)})
            lines(root/'native_route_trace.jsonl', trace)
        positive = audit(first, second)
        assert positive['max_spatial_difference_m'] < 1.0
        negatives = []
        path = second/'route_context.json'
        negatives.append(reject(first, second, path,
                                lambda p: save(p, dict(two, enroute_purpose='none')),
                                'Purpose comparison requires reviewed'))
        negatives.append(reject(first, second, path,
                                lambda p: save(p, dict(two, route_connectivity_source='synthetic changed route')),
                                'Comparison changed route designation'))
        negatives.append(reject(first, second, path,
                                lambda p: save(p, dict(two, vehicle_is_truck=False)),
                                'Comparison changed route designation'))
        negatives.append(reject(first, second, path,
                                lambda p: save(p, dict(two, service_stop_complete=False)),
                                'Missing 100-frame original stop'))
        trace_path = second/'native_route_trace.jsonl'
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
        trace[250]['service_stop_active'] = False
        negatives.append(reject(first, second, trace_path,
                                lambda p: lines(p, trace), 'Missing 100-frame original stop'))
        print(json.dumps({'comparison': positive, 'negative_rejections': negatives}, sort_keys=True))


if __name__ == '__main__':
    main()
