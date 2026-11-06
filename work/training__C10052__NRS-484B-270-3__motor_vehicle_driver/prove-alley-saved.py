"""Exercise the 480-frame alley saved finalizer with source and tamper negatives."""
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
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE/'native'))
spec = importlib.util.spec_from_file_location('saved_fixture', HERE/'saved-fixture-proof.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows))


def build(destination, full_resolution=False):
    fixture.make_base(destination, 'probe_b', full_resolution=full_resolution)
    config = json.loads((HERE/'native/alley-native-config.json').read_text())
    (destination/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    (destination/'facility.mkv').rename(destination/'reference_corner.mkv')
    source = REPO/'.runtime-work/c10052/alley-transition-v1/near_alley'
    geometry = source/'road_geometry.json'
    shutil.copyfile(geometry, destination/'road_geometry.json')
    motion = read_rows(source/'native_samples.jsonl')
    trace = []; evidence = []; history = []; mapping = []
    for index, row in enumerate(motion):
        frame, time = row['native_frame'], row['time_s']
        x,y = row['native_center_xy_m']
        row.update(native_forward_xy=[0,-1], native_road_id=1,
                   native_lane_id=-2 if y <= -3 else -1)
        body = [[a,b,z] for a,b in row['native_body_xy_m'] for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
                      'heading_deg':-90.0,'speed_mps':row['speed_mps']})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'ego':{'body_vertices_m':body}})
        history.append({'frame':frame,'time_s':time,'body_vertices_m':body})
        mapping.append({'video_frame':index,'native_frame':frame,
                        'carla_frame':frame,'time_s':time})
    for name,rows in (('native_samples.jsonl',motion),('trace.jsonl',trace),
        ('capture/evidence.jsonl',evidence),('body_history.jsonl',history),
        ('video_frames.jsonl',mapping)):
        write_rows(destination/name,rows)
    (destination/'alley-transition-sources.json').write_text(json.dumps({
        'format':'c10052-alley-transition-sources-v1',
        'source_kind':'synthetic_cpu_fixture',
        'sha256':{name:sha(destination/name) for name in
                  ('native_samples.jsonl','road_geometry.json')}})+'\n')
    (destination/'context.json').write_text(json.dumps({
        'surveyed_bicycle_facility_and_alley':json.loads(geometry.read_text())})+'\n')
    for channel in config['recording_description']['channels']:
        name = channel['name']; values = []
        for index,row in enumerate(motion):
            if name in ('st.bicycle_lane_or_path','st.driveway_or_alley_entrance'):
                value = json.loads(geometry.read_text())
            elif name == 'rel.occupies': value = row['native_body_xy_m']
            elif name == 'kin.extent': value = {'body_xy_m':row['native_body_xy_m']}
            elif name == 'kin.position': value = row['native_center_xy_m']
            elif name == 'ego_speed': value = row['speed_mps']
            elif name == 'drv.standing_or_parked': value = {'observed_speed_mps':row['speed_mps']}
            elif name == 'ru.pedestrian': value = {'native_actor_id':1,'synthetic_diagnostic':True}
            elif name == 'exception_context': value = {'source':'exception_context.json','observed_exception_status':'unresolved'}
            elif name == 'native_body_pose_control': value = row
            elif name == 'camera_frame_join': value = mapping[index]
            else: raise ValueError('Unknown alley channel '+name)
            values.append({'time_s':row['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)
    return motion


def command(folder, env):
    return subprocess.run([sys.executable, str(HERE/'native/finalize_alley.py'),
        '--attempt',str(folder),'--output',str(folder/'analysis-report.json')],
        cwd=REPO,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)


def run():
    root = Path(tempfile.mkdtemp(dir=REPO/'.runtime-work',prefix='c10052-alley-saved-'))
    base = root/'base'; build(base)
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(REPO/'runtime/pipeline/scenario_pipeline'),
        str(REPO/'runtime/pipeline/python'),str(REPO/'runtime/pipeline'),
        str(HERE/'native'),env.get('PYTHONPATH','')))
    positive = root/'positive';shutil.copytree(base,positive)
    original = fixture.source_hashes(positive)
    success = command(positive,env)
    (root/'positive.log').write_text(success.stdout)
    if success.returncode: raise RuntimeError(success.stdout)
    if fixture.source_hashes(positive) != original:
        raise ValueError('Alley saved finalizer rewrote acquisition')
    report = json.loads((positive/'analysis-report.json').read_text())
    result = json.loads((positive/'result.json').read_text())
    measured = report['measurements']['alley_transition_observation']['value']
    assert measured['first_facility_entry_native_frame'] == 170
    assert measured['first_alley_footprint_native_frame'] == 201
    assert measured['simultaneous_moving_overlap_frames'] == 27
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    negatives = []
    for name,source in (('missing_manifest','alley-transition-sources.json'),
                        ('changed_body','native_samples.jsonl')):
        target = root/name;shutil.copytree(base,target)
        if name == 'missing_manifest': (target/source).unlink()
        else: (target/source).write_bytes((target/source).read_bytes()+b' ')
        failure = command(target,env)
        (root/(name+'.log')).write_text(failure.stdout)
        expected = ('alley-transition-sources.json' if name == 'missing_manifest'
                    else 'Alley transition source hash differs')
        if failure.returncode == 0 or expected not in failure.stdout:
            raise ValueError('Alley saved negative failed: '+name+' '+failure.stdout)
        negatives.append({'name':name,'exit_code':failure.returncode,
                          'log_sha256':sha(root/(name+'.log'))})
    summary = {'format':'c10052-alley-saved-synthetic-proof-v1',
        'source_root':root.relative_to(REPO).as_posix(),
        'positive_report_sha256':sha(positive/'analysis-report.json'),
        'positive_result_sha256':sha(positive/'result.json'),
        'positive_log_sha256':sha(root/'positive.log'),
        'source_hashes':original,'negatives':negatives,
        'selected':False,'accepted':False}
    (HERE/'alley-saved-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
