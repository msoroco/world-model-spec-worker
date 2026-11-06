"""Saved synthetic curb positives and corrupt-source negatives, never Native evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / '.runtime-work/c10316-retained-saved-ur145_b7/reference-positive'
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, allow_nan=False) + '\n' for value in values))


def source_hashes(folder):
    return {str(path.relative_to(folder)): sha(path) for path in folder.rglob('*')
            if path.is_file() and path.name not in ('result.json', 'analysis-report.json')}


def make_base(destination, suffix):
    shutil.copytree(SOURCE, destination)
    for name in ('result.json', 'analysis-report.json', 'native_samples.jsonl', 'crosswalk-context.json'):
        (destination / name).unlink(missing_ok=True)
    for old, new in (('approach.mkv', 'vehicle_approach.mkv'),
                     ('reference_corner.mkv', 'curb_side.mkv'),
                     ('pedestrian_reference.mkv', 'curb_close.mkv')):
        (destination / old).rename(destination / new)
    for path in (destination / 'channels').glob('*.jsonl'):
        path.unlink()
    construction = json.loads((HERE / 'draft-bundles' / suffix / 'primary/construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    (destination / 'config.json').write_text(json.dumps(config) + '\n')
    source = Path(json.loads((HERE / 'curb-summary.json').read_text())['retained_root']) / suffix
    for name in ('curb-samples.jsonl', 'curb-context.json'):
        shutil.copy2(source / name, destination / name)
    context_path = destination / 'curb-context.json'
    context = json.loads(context_path.read_text())
    context['introductory_exceptions'] = 'unreviewed_synthetic_context'
    context_path.write_text(json.dumps(context) + '\n')
    shutil.copy2(HERE / 'native/road.xodr', destination / 'road.xodr')
    samples = read_rows(destination / 'curb-samples.jsonl')
    trace = read_rows(destination / 'trace.jsonl')
    evidence = read_rows(destination / 'capture/evidence.jsonl')
    mapping = read_rows(destination / 'video_frames.jsonl')
    native = read_rows(destination / 'capture/native/frames.jsonl')
    if not all(len(values) == 240 for values in (samples, trace, evidence, mapping, native)):
        raise ValueError('Retained curb base lacks 240 frames')
    channels = {item['name']: [] for item in config['recording_description']['channels']}
    prior_speed = None
    for index, (sample, t, e, m, n) in enumerate(zip(samples, trace, evidence, mapping, native)):
        frame, time = sample['native_frame'], sample['time_s']
        x, y = sample['pedestrian_xy_m']
        body = sample['pedestrian_footprint_xy_m']
        body3 = [[point[0], point[1], z] for point in body for z in (0, 1.8)]
        t.update(frame=frame, time_s=time, position={'x': x, 'y': y, 'z': .5},
                 position_m=[x, y, .5], heading_deg=0, synthetic_diagnostic=True)
        e.update(original_frame=frame, replay_frame=frame, recording_time_s=time,
                 replay_simulation_time_s=time, synthetic_diagnostic=True)
        e['ego'].update(position_m=[x, y, .5], heading_deg=0, body_vertices_m=body3,
                        speed_provenance='synthetic_request_not_native')
        m.update(video_frame=index, native_frame=frame, carla_frame=frame, time_s=time)
        n.update(frame=frame, time_s=time, simulation_time=time, synthetic_diagnostic=True)
        ped_speed = sample['pedestrian_speed_mps']
        accel = 0 if prior_speed is None else (ped_speed-prior_speed)/.05
        prior_speed = ped_speed
        values = {'kin.position': [x, y],
                  'kin.speed': {'pedestrian_mps': ped_speed, 'vehicle_mps': sample['vehicle_speed_mps']},
                  'kin.accel_longitudinal': accel,
                  'rel.occupies': {'original_footprint_xy_m': body, 'curb_edge_x_m': -3.5},
                  'drv.time_to_conflict': (-sample['vehicle_xy_m'][1])/sample['vehicle_speed_mps'],
                  'drv.stopping_distance': {'conditional_assumption_only': True,
                      'reaction_s': [.8, 1.2], 'deceleration_mps2': [3, 5]},
                  'curb_camera_frame_join': m}
        for name in channels:
            channels[name].append({'time_s': time, 'value': values[name]})
    for name, values in (('trace.jsonl', trace), ('capture/evidence.jsonl', evidence),
                         ('video_frames.jsonl', mapping), ('capture/native/frames.jsonl', native)):
        write_rows(destination / name, values)
    for name, values in channels.items():
        write_rows(destination / 'channels' / (name + '.jsonl'), values)
    manifest_path = destination / 'capture/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['sources'] = {'trace.jsonl': sha(destination / 'trace.jsonl'),
                           'road.xodr': sha(destination / 'road.xodr')}
    manifest['synthetic_diagnostic'] = True
    manifest_path.write_text(json.dumps(manifest) + '\n')
    return config


def run_finalizer(folder, env):
    return subprocess.run([sys.executable, str(HERE / 'native/finalize.py'),
                           '--attempt', str(folder), '--output', str(folder / 'analysis-report.json')],
                          env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)


def main():
    if not SOURCE.is_dir():
        raise RuntimeError('Adjacent retained synthetic video source is missing')
    env = dict(os.environ)
    env['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'runtime/pipeline/scenario_pipeline'),
        str(ROOT / 'runtime/pipeline/python'), str(ROOT / 'runtime/pipeline'),
        str(HERE / 'native'), env.get('PYTHONPATH', '')))
    retained = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c230222-curb-saved-'))
    records = []
    for suffix in ('probe_1', 'probe_2'):
        base = retained / (suffix + '-base')
        config = make_base(base, suffix)
        variants = {name: retained / (suffix + '-' + name) for name in
                    ('positive', 'missing', 'wrong-footprint', 'missing-video')}
        for folder in variants.values():
            shutil.copytree(base, folder)
        positive = variants['positive']
        before = source_hashes(positive)
        success = run_finalizer(positive, env)
        if success.returncode:
            raise RuntimeError('Saved curb positive failed: ' + success.stdout)
        if source_hashes(positive) != before:
            raise RuntimeError('Curb finalizer rewrote original acquisition')
        report = json.loads((positive / 'analysis-report.json').read_text())
        result = json.loads((positive / 'result.json').read_text())
        contract = json.loads((HERE / 'draft-curb' / suffix / 'measurement-contract.json').read_text())
        verify_report(contract, report, positive)
        if result['accepted'] or result['legal_verdict_claimed'] or result['setup_confirmed'] or result['behavior_attempted']:
            raise RuntimeError('Synthetic curb acquired physical or legal status')
        (variants['missing'] / 'curb-samples.jsonl').unlink()
        wrong = variants['wrong-footprint']
        wrong_rows = read_rows(wrong / 'capture/evidence.jsonl')
        wrong_rows[10]['ego']['body_vertices_m'][0][0] += 1
        write_rows(wrong / 'capture/evidence.jsonl', wrong_rows)
        (variants['missing-video'] / 'overview.mkv').unlink()
        errors = []
        for name, expected in (('missing', 'Missing required source: curb-samples.jsonl'),
                               ('wrong-footprint', 'Original curb pedestrian footprint differs'),
                               ('missing-video', 'Missing required source: overview.mkv')):
            failure = run_finalizer(variants[name], env)
            if failure.returncode == 0 or expected not in failure.stdout:
                raise RuntimeError('Curb negative did not reject: ' + name + ' ' + failure.stdout)
            errors.append(expected)
        records.append({'case_id': config['case_id'], 'case_suffix': suffix, 'frames': 240,
                        'positive_exit_code': 0, 'negative_errors': errors,
                        'conditional_yield_relation': result['measured_values']['conditional_yield_relation'],
                        'source_unchanged': True, 'video_sources_decoded': 4,
                        'retained_positive': str(positive), 'original_source_hashes': before,
                        'analysis_report_sha256': sha(positive / 'analysis-report.json'),
                        'result_sha256': sha(positive / 'result.json'),
                        'scope': 'synthetic saved-source diagnostic; no Native or accepted recording'})
    summary = {'format': 'c230222-retained-curb-saved-proof-v1',
               'retained_root': str(retained), 'records': records}
    (HERE / 'saved-curb-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'cases': 2, 'frames_per_case': 240, 'video_sources_per_case': 4,
                      'negative_rejections': 6, 'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
