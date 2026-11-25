"""Exercise both saved finalizers with joined synthetic route sources."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from measure_through_route import AID, CAMERAS, COUNT

HERE = Path(__file__).resolve().parent


def save(path, values):
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


def run(case, bundle, root, hashes):
    (root/'config.json').write_bytes((HERE/bundle/'config.json').read_bytes())
    frames = [{'video_frame': i, 'native_frame': 1000+i, 'carla_frame': 1000+i,
               'time_s': round(i*.05, 4)} for i in range(COUNT)]
    save(root/'video_frames.jsonl', frames)
    context = {'assignment_id': AID, 'case_id': AID+'__'+case,
               'review_kind': 'synthetic_diagnostic', 'reviewer': 'synthetic-software-test',
               'camera_sha256': hashes, 'truck_blueprint_source': 'synthetic fixture',
               'truck_route_designation_source': 'synthetic fixture',
               'nontruck_street_designation_source': 'synthetic fixture',
               'route_connectivity_source': 'synthetic fixture',
               'enroute_purpose_source': 'synthetic fixture',
               'served_premises_source': 'synthetic fixture',
               'entry_truck_route_id': 100, 'intervening_street_id': 200,
               'exit_truck_route_id': 300, 'ego_actor_id': 7, 'vehicle_is_truck': True,
               'enroute_purpose': 'none' if case == 'probe_01' else 'delivery',
               'service_stop_complete': case == 'probe_02'}
    (root/'route_context.json').write_text(json.dumps(context)+'\n')
    trace = []
    for i in range(COUNT):
        x = (i if case == 'probe_01' or i < 220 else 220 if i < 320 else i-100)*.1
        stopped = case == 'probe_02' and 220 <= i < 320
        trace.append({'video_frame': i, 'native_frame': 1000+i,
                      'source_kind': 'synthetic_native_sample', 'ego_actor_id': 7,
                      'road_id': 100 if i < 150 else 200 if i < 450 else 300,
                      'ego_x_m': round(x, 4), 'ego_y_m': 0.0,
                      'ego_speed_mps': 0.0 if stopped else 2.0,
                      'service_stop_active': stopped})
    save(root/'native_route_trace.jsonl', trace)
    save(root/'trace.jsonl', [{'frame': 1000+i, 'time_s': round(i*.05, 4),
                              'position': {'x': r['ego_x_m'], 'y': 0.0, 'z': 0.0},
                              'position_m': [r['ego_x_m'], 0.0, 0.0],
                              'heading_deg': 0.0, 'speed_mps': r['ego_speed_mps']}
                             for i,r in enumerate(trace)])
    command = [sys.executable, str(HERE/bundle/'finalize.py'), '--attempt', str(root),
               '--output', str(root/'analysis-report.json')]
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path('runtime/scenario_pipeline').resolve())
    positive = subprocess.run(command, text=True, capture_output=True, env=env)
    if positive.returncode:
        raise AssertionError(positive.stdout+positive.stderr)
    report = json.loads((root/'analysis-report.json').read_text())
    result = json.loads((root/'result.json').read_text())
    expected = 'complete_truck_route_passage' if case == 'probe_01' else 'documented_service_passage'
    assert report['measurements'][expected]['value'] is True
    assert len(result['recording_evidence']) == 7
    (root/'route_context.json').unlink()
    (root/'result.json').unlink()
    (root/'analysis-report.json').unlink()
    negative = subprocess.run(command, text=True, capture_output=True, env=env)
    assert negative.returncode and 'Missing required source: route_context.json' in negative.stderr
    return {'case': case, 'measurement': expected, 'source_join_passed': True,
            'missing_case_source_rejected': True}


def main():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        base = Path(tmp)
        for name in CAMERAS:
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=c=black:s=64x48:r=20', '-frames:v', str(COUNT),
                            '-c:v', 'ffv1', str(base/(name+'.mkv'))], check=True)
        hashes = {name+'.mkv': hashlib.sha256((base/(name+'.mkv')).read_bytes()).hexdigest()
                  for name in CAMERAS}
        results = []
        for case,bundle in [('probe_01','selected_primary'),('probe_02','selected_purpose')]:
            root = base/case
            root.mkdir()
            for name in CAMERAS:
                (root/(name+'.mkv')).hardlink_to(base/(name+'.mkv'))
            results.append(run(case,bundle,root,hashes))
        print(json.dumps({'diagnostic_only': True, 'finalizers': results}, sort_keys=True))


if __name__ == '__main__':
    main()
