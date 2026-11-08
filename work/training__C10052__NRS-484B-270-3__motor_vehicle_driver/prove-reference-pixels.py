"""Controlled RGB/instance videos for saved reference-view visibility."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]/'.runtime-work/c10052-reference-pixel-sources'
WIDTH,HEIGHT=64,36
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def write(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')
def write_rows(path,values):path.write_text(''.join(json.dumps(v,sort_keys=True)+'\n' for v in values))

def encode(path,frames):
    path.unlink(missing_ok=True)
    process=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
        '-f','rawvideo','-pix_fmt','rgb24','-s',f'{WIDTH}x{HEIGHT}','-r','20',
        '-i','pipe:0','-an','-c:v','ffv1','-level','1',str(path)],
        stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    for frame in frames:process.stdin.write(frame.tobytes())
    process.stdin.close()
    error=process.stderr.read().decode()
    if process.wait(timeout=120):raise RuntimeError(error)

def fixture(name,samples):
    folder=ROOT/name;folder.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HERE/'no-entry-sources/native_samples.jsonl',folder/'native_samples.jsonl')
    mapping=[{'video_frame':i,'native_frame':row['native_frame'],
              'carla_frame':row['native_frame'],'time_s':row['time_s']}
             for i,row in enumerate(samples)]
    write_rows(folder/'video_frames.jsonl',mapping)
    rgb_frames=[];instance_frames=[]
    for row in samples:
        x=row['native_center_xy_m'][0]
        rgb=np.full((HEIGHT,WIDTH,3),120,dtype=np.uint8)
        rgb[11:26,20:45]=120 if name=='primary' and -10<=x<=-6 else 200
        instance=np.zeros((HEIGHT,WIDTH,3),dtype=np.uint8)
        instance[11:26,20:45]=[14,1,7]
        rgb_frames.append(rgb);instance_frames.append(instance)
    encode(folder/'reference_corner.mkv',rgb_frames)
    encode(folder/'reference_instance.mkv',instance_frames)
    write(folder/'reference-pixel-sources.json',{
        'format':'c10052-reference-pixel-sources-v1','source_kind':'synthetic_cpu_fixture',
        'width':WIDTH,'height':HEIGHT,
        'sha256':{p:sha(folder/p) for p in ('reference_corner.mkv','reference_instance.mkv',
            'video_frames.jsonl','native_samples.jsonl')}})
    return folder

def main():
    spec=importlib.util.spec_from_file_location('reference_pixels',HERE/'native/measure_reference_pixels.py')
    meter=importlib.util.module_from_spec(spec);spec.loader.exec_module(meter)
    samples=rows(HERE/'no-entry-sources/native_samples.jsonl')
    ROOT.mkdir(exist_ok=True)
    positives=[]
    for name in ('primary','wide'):
        folder=fixture(name,samples)
        measured=meter.measure(folder)
        if measured['body_visible_fraction']>=.95 if name=='primary' else measured['body_visible_fraction']!=1.0:
            raise ValueError('Controlled reference pixel contrast differs')
        positives.append({'name':name,'measurement':measured,
            'manifest_sha256':sha(folder/'reference-pixel-sources.json')})
    if positives[0]['measurement']['route_window_frames']!=positives[1]['measurement']['route_window_frames']:
        raise ValueError('Controlled reference window differs')
    manifest=json.loads((HERE/'draft-no-entry-execution-manifest.json').read_text())
    entry=manifest['cases'][0]
    exact=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        ref=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
        construction_path=HERE/ref['construction']
        if sha(construction_path)!=ref['construction_sha256']:
            raise ValueError('Exact reference pixel construction hash differs')
        construction=json.loads(construction_path.read_text())
        content=next(x['content'] for x in construction['files'] if x['path']=='measure_reference_pixels.py')
        exact_folder=ROOT/'exact'/candidate;exact_folder.mkdir(parents=True,exist_ok=True)
        exact_path=exact_folder/'measure_reference_pixels.py';exact_path.write_text(content)
        exact_spec=importlib.util.spec_from_file_location('exact_reference_pixels_'+candidate,exact_path)
        exact_meter=importlib.util.module_from_spec(exact_spec);exact_spec.loader.exec_module(exact_meter)
        measures={name:exact_meter.measure(ROOT/name)['body_visible_fraction'] for name in ('primary','wide')}
        if measures!={'primary':positives[0]['measurement']['body_visible_fraction'],
                     'wide':positives[1]['measurement']['body_visible_fraction']}:
            raise ValueError('Exact reference pixel processor differs')
        exact.append({'candidate':candidate,'construction_sha256':sha(construction_path),
                      'meter_sha256':sha(exact_path),'fractions':measures})
    original=ROOT/'primary';negative=ROOT/'negative'
    if negative.exists():shutil.rmtree(negative)
    shutil.copytree(original,negative)
    (negative/'reference_corner.mkv').write_bytes((negative/'reference_corner.mkv').read_bytes()+b' ')
    try:meter.measure(negative)
    except ValueError as error:
        if 'Reference pixel source hash differs' not in str(error):raise
    else:raise ValueError('Changed RGB source was accepted')
    shutil.rmtree(negative)
    proof={'format':'c10052-reference-pixel-controlled-proof-v1','passed':True,
        'meter_sha256':sha(HERE/'native/measure_reference_pixels.py'),
        'manifest_sha256':sha(HERE/'draft-no-entry-execution-manifest.json'),
        'positives':positives,'exact_candidates':exact,'changed_rgb_negative':True,
        'source_kind':'synthetic_cpu_fixture','original_native_claimed':False}
    write(HERE/'reference-pixel-proof.json',proof)
    return proof

if __name__=='__main__':
    proof=main();print(json.dumps({'passed':True,
        'fractions':{x['name']:x['measurement']['body_visible_fraction'] for x in proof['positives']}},indent=2))
