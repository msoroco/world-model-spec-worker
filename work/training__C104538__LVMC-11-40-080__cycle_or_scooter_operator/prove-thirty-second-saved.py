"""Build a 600-frame raw-source bicycle diagnostic and run saved-only processing."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT/'.runtime-work'
if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '').startswith(str(SCRATCH)):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before importing runtime')
sys.path.insert(0, str(ROOT/'runtime/scenario_pipeline'))
sys.path.insert(0, str(HERE/'native'))
from worker_exchange.runtime_cli import materialize
from thirty_second import rows as rider_rows, validate as validate_rider
from geometry import open_drive

motor_path = ROOT/'work/training__C104538__NRS-484B-403-2__motor_vehicle_driver/probe-core-synthetic.py'
spec = importlib.util.spec_from_file_location('c104538_motor_fixture', motor_path)
motor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motor)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_rows(path, values):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(''.join(json.dumps(value, allow_nan=False)+'\n' for value in values))


def build(destination, kind='mounted_turn', candidate='primary', manifest=None):
    if destination.exists():
        raise ValueError('Use a fresh diagnostic destination')
    if kind not in ('mounted_obey', 'mounted_turn', 'dismounted_turn'):
        raise ValueError('Unknown rider case')
    case = HERE.name+({'mounted_obey': '__controlled_1',
                       'mounted_turn': '__controlled_2',
                       'dismounted_turn': '__controlled_3'}[kind])
    manifest = Path(manifest) if manifest is not None else HERE/'draft-thirty-second-execution-manifest.json'
    motor_attempt = motor.make_attempt(destination.parent/'motor', 'witness_2')
    materialize(manifest, case, destination)
    for name in ('native_samples.jsonl', 'video_frames.jsonl', 'body_history.jsonl',
                 'trace.jsonl'):
        shutil.copyfile(motor_attempt/name, destination/name)
    for name, width, height in (('overview', 1920, 1080), ('approach', 1280, 720),
                                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)):
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r=20:d=30',
                        '-frames:v', '600', '-c:v', 'ffv1', '-pix_fmt', 'yuv444p',
                        str(destination/(name+'.mkv'))], check=True, timeout=360)
    shutil.copytree(motor_attempt/'capture', destination/'capture')
    rider = rider_rows(kind, candidate)
    validate_rider(rider, kind, candidate)
    native = read_rows(destination/'native_samples.jsonl')
    mapping = read_rows(destination/'video_frames.jsonl')
    trace = read_rows(destination/'trace.jsonl')
    evidence = read_rows(destination/'capture/evidence.jsonl')
    history = read_rows(destination/'body_history.jsonl')
    if any(len(part) != 600 for part in (rider, native, mapping, trace, evidence, history)):
        raise ValueError('Six raw source streams must contain 600 frames')
    for i, (r, n, m, t, e, b) in enumerate(zip(rider, native, mapping, trace, evidence, history)):
        r['time_s'] = n['time_s']
        x, y = r['x_m'], r['y_m']
        before, after = rider[max(0, i-1)], rider[min(599, i+1)]
        dx, dy = after['x_m']-before['x_m'], after['y_m']-before['y_m']
        length = math.hypot(dx, dy)
        direction = [dx/length, dy/length] if length > 1e-8 else [1.0, 0.0]
        velocity = [dx * 10.0, dy * 10.0, 0.0]
        corners = [[round(x+sx, 6), round(y+sy, 6)] for sx, sy in
                   ((-1, -.35), (-1, .35), (1, .35), (1, -.35))]
        body3 = [[a, c, z] for a, c in corners for z in (0, 1.5)]
        n.update(native_center_xy_m=[x, y], native_forward_xy=direction,
                 native_body_xy_m=corners, native_lane_id=-1 if y >= 0 else 1)
        t.update(position={'x': x, 'y': y, 'z': .5}, position_m=[x, y, .5],
                 heading_deg=math.degrees(math.atan2(direction[1], direction[0])),
                 velocity_mps=velocity)
        e['ego'].update(body_vertices_m=body3, position_m=[x, y, .5],
                        heading_deg=t['heading_deg'])
        e['world']['road_projection']['lane_id'] = n['native_lane_id']
        b['body_vertices_m'] = body3
        assert m['native_frame'] == n['native_frame'] and m['time_s'] == n['time_s']
    for name, values in (('rider_native_samples.jsonl', rider), ('native_samples.jsonl', native),
                         ('trace.jsonl', trace), ('capture/evidence.jsonl', evidence),
                         ('body_history.jsonl', history)):
        write_rows(destination/name, values)
    shutil.copyfile(HERE/'draft-native-sources/authored-sign.json', destination/'authored-sign.json')
    (destination/'road.xodr').write_text(open_drive())
    capture = json.loads((destination/'capture/manifest.json').read_text())
    capture['sources']['trace.jsonl'] = sha(destination/'trace.jsonl')
    capture['sources']['road.xodr'] = sha(destination/'road.xodr')
    capture['synthetic_diagnostic'] = True
    (destination/'capture/manifest.json').write_text(json.dumps(capture, allow_nan=False)+'\n')
    (destination/'capture/recorder_info.txt').write_text('Create 107: vehicle.bh.crossbike\n')
    source_manifest = {'source_kind': 'synthetic_native_shaped_diagnostic',
                       'case_suffix': kind, 'candidate_id': candidate,
                       'rider_samples_sha256': sha(destination/'rider_native_samples.jsonl'),
                       'sign_sha256': sha(destination/'authored-sign.json'),
                       'original_native_capture_executed': False}
    (destination/'rider-source-manifest.json').write_text(json.dumps(source_manifest, indent=2)+'\n')
    if (destination/'channels').exists() or (destination/'context.json').exists():
        raise ValueError('Raw diagnostic must not carry derived channels')
    return case, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--kind', choices=('mounted_obey', 'mounted_turn', 'dismounted_turn'), default='mounted_turn')
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2'), default='primary')
    parser.add_argument('--manifest')
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    attempt = out/'attempt'
    case, manifest = build(attempt, args.kind, args.candidate, args.manifest)
    command = [sys.executable, str(ROOT/'runtime.py'), 'process-saved', '--manifest', str(manifest),
               '--case', case, '--attempt', str(attempt), '--output', str(out/'saved'),
               '--library', str(ROOT/'runtime/library'),
               '--validator', str(ROOT/'.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck')]
    run = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=900)
    (out/'process-saved.log').write_text(run.stdout)
    if run.returncode:
        raise RuntimeError(run.stdout[-4000:])
    receipt = json.loads(run.stdout)
    if not (receipt['passed'] and receipt['recorded_only'] and receipt['originals_preserved']
            and not receipt['missing_evidence'] and not receipt['physical_acceptance_claimed']):
        raise ValueError('Saved diagnostic receipt incomplete')
    negatives = {}
    for label in ('missing_rider', 'changed_time_join'):
        negative = out/(label+'-attempt')
        shutil.copytree(attempt, negative)
        if label == 'missing_rider':
            (negative/'rider_native_samples.jsonl').unlink()
            expected = 'Missing required source: rider_native_samples.jsonl'
        else:
            source = negative/'native_samples.jsonl'
            values = read_rows(source)
            values[220]['time_s'] += .05
            write_rows(source, values)
            expected = 'Rider/sign/frame source join differs'
        failed = subprocess.run([sys.executable, str(negative/'finalize.py'), '--attempt',
                                 str(negative), '--output', str(negative/'analysis-report.json')],
                                cwd=negative, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=300)
        log = out/(label+'.log')
        log.write_text(failed.stdout)
        if failed.returncode == 0 or expected not in failed.stdout:
            raise ValueError(label+' negative failed: '+failed.stdout[-1500:])
        negatives[label] = {'exit_code': failed.returncode, 'expected_error': expected,
                            'log_sha256': sha(log)}
    report = {'format': 'c104538-600-frame-saved-diagnostic-v1', 'passed': True,
              'case_id': case, 'frames': receipt['timestamp_joins']['frames'],
              'manifest_sha256': sha(manifest), 'construction_sha256': sha(attempt/'construction.json'),
              'process_saved_log_sha256': sha(out/'process-saved.log'),
              'analysis_log_sha256': receipt['analysis_log_sha256'],
              'originals_preserved': receipt['originals_preserved'],
              'missing_evidence': receipt['missing_evidence'],
              'negative_checks': negatives,
              'scope': 'synthetic raw-source software diagnostic; no original Native capture or legal finding'}
    if report['frames'] != 600:
        raise ValueError('Saved processor did not join all 600 frames')
    (out/'summary.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
