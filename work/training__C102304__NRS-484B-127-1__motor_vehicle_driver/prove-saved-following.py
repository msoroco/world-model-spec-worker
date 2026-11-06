"""Full-window synthetic saved-source positives/negatives; no Native claim."""
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
sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0, str(HERE/'native'))
from worker_exchange.measurement_contract import verify_report
from batch_pipeline.carla import validate_attempt
from geometry import open_drive


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows))


def source_hashes(folder):
    return {str(path.relative_to(folder)): sha(path) for path in folder.rglob('*')
            if path.is_file() and path.name not in ('result.json','analysis-report.json')}


def make_base(destination, suffix, env, full_resolution=False):
    destination.mkdir()
    (destination/'capture/native').mkdir(parents=True)
    (destination/'channels').mkdir()
    construction = json.loads((HERE/'draft-candidates'/suffix/'primary/construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    (destination/'config.json').write_text(json.dumps(config)+'\n')
    source = HERE/'draft-following'/suffix
    shutil.copy2(source/'native_samples.jsonl', destination/'native_samples.jsonl')
    shutil.copy2(source/'following_context.json', destination/'following_context.json')
    samples = [json.loads(line) for line in (destination/'native_samples.jsonl').read_text().splitlines()]
    trace, evidence, mapping, native_frames = [], [], [], []
    channel_values = {item['name']: [] for item in config['recording_description']['channels']}
    for i, item in enumerate(samples):
        frame, time = 100+i, item['time_s']
        ego, lead = item['ego'], item['lead']
        item['native_frame'] = frame
        x = (ego['native_body_xy_m'][0][0]+ego['native_body_xy_m'][2][0])/2
        y = (ego['native_body_xy_m'][0][1]+ego['native_body_xy_m'][2][1])/2
        body = [[p[0],p[1],z] for p in ego['native_body_xy_m'] for z in (0,1.5)]
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': x, 'y': y, 'z': .5},
                      'position_m': [x,y,.5], 'heading_deg': 0,
                      'speed_mps': ego['speed_mps'], 'speed_mph': ego['speed_mps']/.44704,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False},
                      'synthetic_diagnostic': True})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': [x,y,.5], 'heading_deg': 0,
                                 'speed_mps': ego['speed_mps'],
                                 'speed_provenance': 'original_trace_actor_get_velocity',
                                 'body_vertices_m': body},
                         'synthetic_diagnostic': True,
                         'world': {'weather': {'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                                   'road_projection': {'road_id':1,'section_id':0,'lane_id':-1,'s_m':x+100}}})
        mapping.append({'video_frame': i, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time})
        native_frames.append({'frame': frame, 'time_s': time, 'simulation_time': time,
                              'base': f'graphs/base/{frame:08d}.pkl',
                              'abstract': f'graphs/abstract/{frame:08d}.pkl',
                              'synthetic_diagnostic': True})
        gap = min(p[0] for p in lead['native_body_xy_m'])-max(p[0] for p in ego['native_body_xy_m'])
        values = {'kin.speed': {'ego_mps': ego['speed_mps'], 'lead_mps': lead['speed_mps']},
                  'st.lane': {'ego': [1,-1], 'lead': [1,-1]},
                  'rel.surface_gap': {'longitudinal_bumper_gap_m': gap},
                  'rel.ahead_behind_in_lane': {'ego_behind_lead': True, 'same_lane': True},
                  'native_body_pose_control': item,
                  'camera_frame_join': mapping[-1]}
        for name in channel_values:
            channel_values[name].append({'time_s': time, 'value': values[name]})
    write_rows(destination/'native_samples.jsonl', samples)
    for name, records in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                          ('video_frames.jsonl',mapping),('capture/native/frames.jsonl',native_frames)]:
        write_rows(destination/name, records)
    for name, records in channel_values.items():
        write_rows(destination/'channels'/(name+'.jsonl'), records)
    (destination/'road.xodr').write_text(open_drive())
    (destination/'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (destination/'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 900, 'required_observations': [],
        'sources': {'trace.jsonl': sha(destination/'trace.jsonl'),
                    'road.xodr': sha(destination/'road.xodr')},
        'synthetic_diagnostic': True})+'\n')
    for camera in config['cameras']:
        size = f"{camera['width']}x{camera['height']}" if full_resolution else '32x32'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d=45',
            '-frames:v','900','-c:v','ffv1',str(destination/(camera['name']+'.mkv'))],
            check=True,env=env,timeout=120)
    return construction, config


def main():
    env = dict(os.environ)
    env['PATH'] = str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    os.environ['PATH'] = env['PATH']
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),
        str(HERE/'native'),env.get('PYTHONPATH','')))
    records = []
    retained = Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work', prefix='c102304-retained-saved-'))
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c102304-saved-') as temporary:
        scratch = Path(temporary)
        for suffix in ('condition_a','condition_b'):
            base = scratch/(suffix+'-base')
            construction, config = make_base(base, suffix, env)
            positive, missing, wrong = (scratch/(suffix+label) for label in ('-positive','-missing','-wrong-lane'))
            for destination in (positive, missing, wrong):
                shutil.copytree(base, destination)
            before = source_hashes(positive)
            command = [sys.executable,str(HERE/'native/finalize.py'),
                       '--attempt',str(positive),'--output',str(positive/'analysis-report.json')]
            success = subprocess.run(command, env=env, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            if success.returncode:
                raise RuntimeError('Saved positive failed: '+success.stdout)
            if source_hashes(positive) != before:
                raise RuntimeError('Finalizer rewrote original source')
            report = json.loads((positive/'analysis-report.json').read_text())
            result = json.loads((positive/'result.json').read_text())
            contract = json.loads((HERE/'draft-following'/suffix/'measurement-contract.json').read_text())
            verify_report(contract, report, positive)
            validated = validate_attempt(positive, {'case': {
                'case_id': result['case_id'], 'recording_description': config['recording_description'],
                'sweep_measurements': []}, 'cell': {'cell_id':'C102304'},
                'actor': 'motor_vehicle_driver'}, construction, {'recorded_exit_code':0}, {})
            if not validated['rebuild_required'] or result['accepted']:
                raise RuntimeError('Synthetic saved case asserted acceptance')
            (missing/'native_samples.jsonl').unlink()
            rows = [json.loads(line) for line in (wrong/'native_samples.jsonl').read_text().splitlines()]
            rows[10]['lead']['native_lane_id'] = 1
            write_rows(wrong/'native_samples.jsonl', rows)
            negative_errors = []
            for folder, expected in ((missing,'Missing required source: native_samples.jsonl'),
                                     (wrong,'Original following lane differs')):
                failure = subprocess.run([sys.executable,str(HERE/'native/finalize.py'),
                    '--attempt',str(folder),'--output',str(folder/'analysis-report.json')],
                    env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
                if failure.returncode == 0 or expected not in failure.stdout:
                    raise RuntimeError('Saved negative did not reject: '+failure.stdout)
                negative_errors.append(expected)
            for name, folder in (('positive',positive),('missing',missing),('wrong-lane',wrong)):
                shutil.copytree(folder,retained/(suffix+'-'+name))
            records.append({'case_id': result['case_id'], 'case_suffix': suffix,
                            'frames': 900, 'positive_exit_code': 0,
                            'negative_exit_codes': [1,1], 'negative_errors': negative_errors,
                            'measured_gap_m': report['measurements']['moving_following_interval']['value']['median_bumper_gap_m'],
                            'video_sources_decoded': 4, 'source_unchanged': True,
                            'native_attempt_validator_passed': True, 'rebuild_required': True,
                            'retained_positive': str(retained/(suffix+'-positive')),
                            'retained_missing': str(retained/(suffix+'-missing')),
                            'retained_wrong_lane': str(retained/(suffix+'-wrong-lane')),
                            'original_source_hashes': before,
                            'analysis_report_sha256': sha(positive/'analysis-report.json'),
                            'result_sha256': sha(positive/'result.json'),
                            'scope': '900-frame synthetic saved diagnostic; no Native or accepted recording'})
    (HERE/'saved-following-summary.json').write_text(json.dumps({
        'format':'c102304-retained-synthetic-saved-proof-v1',
        'retained_root':str(retained), 'records':records},indent=2)+'\n')
    print(json.dumps({'cases':len(records),'frames_per_case':900,'video_sources_per_case':4,
                      'negative_rejections':4,'accepted_recordings':0},sort_keys=True))


if __name__ == '__main__':
    main()
