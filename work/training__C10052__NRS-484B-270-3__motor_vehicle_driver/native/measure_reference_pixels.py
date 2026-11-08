"""Source-bound reference-camera body contrast from paired original videos."""
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def read_frame(stream,size):
    chunks=[];remaining=size
    while remaining:
        part=stream.read(remaining)
        if not part:break
        chunks.append(part);remaining-=len(part)
    return b''.join(chunks)

def decode(path):
    return subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
        '-i',str(path),'-f','rawvideo','-pix_fmt','rgb24','-'],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)

def contrast(rgb,mask):
    count=int(mask.sum())
    if count<4:return count,0.0,False
    ys,xs=np.where(mask)
    left=max(0,int(xs.min())-5);right=min(mask.shape[1],int(xs.max())+6)
    top=max(0,int(ys.min())-5);bottom=min(mask.shape[0],int(ys.max())+6)
    local=mask[top:bottom,left:right]
    rim=np.ones(local.shape,dtype=bool)
    rim[2:-2,2:-2]=False
    rim &= ~local
    if not rim.any():return count,0.0,False
    luminance=rgb.astype(np.float32)@np.array([.2126,.7152,.0722],dtype=np.float32)
    target=float(np.median(luminance[mask]))
    background=float(np.median(luminance[top:bottom,left:right][rim]))
    value=abs(target-background)/max(1.0,background)
    return count,round(value,6),value>=.05

def measure(folder):
    folder=Path(folder)
    manifest_path=folder/'reference-pixel-sources.json'
    if not manifest_path.is_file():raise ValueError('Missing required source: reference-pixel-sources.json')
    manifest=json.loads(manifest_path.read_text())
    if manifest.get('format')!='c10052-reference-pixel-sources-v1' or manifest.get('source_kind') not in ('synthetic_cpu_fixture','original_native'):
        raise ValueError('Unknown reference pixel source provenance')
    expected=manifest.get('sha256',{})
    names={'reference_corner.mkv','reference_instance.mkv','video_frames.jsonl','native_samples.jsonl'}
    if set(expected)!=names:raise ValueError('Incomplete reference pixel source hashes')
    for name,digest in expected.items():
        if not (folder/name).is_file() or sha(folder/name)!=digest:
            raise ValueError('Reference pixel source hash differs: '+name)
    width,height=manifest.get('width'),manifest.get('height')
    if type(width) is not int or type(height) is not int or width<32 or height<24:
        raise ValueError('Invalid reference pixel dimensions')
    frames=rows(folder/'video_frames.jsonl');samples=rows(folder/'native_samples.jsonl')
    if len(frames)!=480 or len(samples)!=480:raise ValueError('Reference pixel frame count differs')
    for index,(frame,sample) in enumerate(zip(frames,samples)):
        if (frame.get('video_frame')!=index or
            frame.get('native_frame')!=sample.get('native_frame') or
            frame.get('time_s')!=sample.get('time_s') or
            (manifest['source_kind']=='original_native' and sample.get('synthetic_diagnostic'))):
            raise ValueError('Reference pixel original frame join differs')
    rgb_process=decode(folder/'reference_corner.mkv')
    instance_process=decode(folder/'reference_instance.mkv')
    measured=[];size=width*height*3
    try:
        for index,frame in enumerate(frames):
            rgb_data=read_frame(rgb_process.stdout,size)
            mask_data=read_frame(instance_process.stdout,size)
            if len(rgb_data)!=size or len(mask_data)!=size:
                raise ValueError('Reference pixel video frame count differs')
            rgb=np.frombuffer(rgb_data,dtype=np.uint8).reshape(height,width,3)
            instance=np.frombuffer(mask_data,dtype=np.uint8).reshape(height,width,3)
            tags=instance[:,:,0]
            vehicle=(tags==10)|(tags==14)
            codes=instance[:,:,1].astype(np.uint16)*256+instance[:,:,2].astype(np.uint16)
            present=np.unique(codes[vehicle& (codes!=0)])
            if len(present)>1:raise ValueError('Reference pixel video has multiple vehicle instances')
            body=vehicle & (codes==present[0]) if len(present)==1 else np.zeros(vehicle.shape,dtype=bool)
            pixels,value,visible=contrast(rgb,body)
            measured.append({'native_frame':frame['native_frame'],'time_s':frame['time_s'],
                'target_pixels':pixels,'weber_contrast':value,'body_visible':visible})
        if read_frame(rgb_process.stdout,1) or read_frame(instance_process.stdout,1):
            raise ValueError('Reference pixel video has extra frames')
        if rgb_process.wait(timeout=30) or instance_process.wait(timeout=30):
            raise ValueError('Reference pixel video decoder failed')
    finally:
        for process in (rgb_process,instance_process):
            if process.poll() is None:process.kill()
            process.stdout.close();process.stderr.close()
    region=[row['body_visible'] for row,sample in zip(measured,samples)
            if -20<=sample['native_center_xy_m'][0]<=10]
    if len(region)<20:raise ValueError('Reference pixel route window lacks frames')
    return {'format':'c10052-reference-pixel-measurement-v1',
        'source_kind':manifest['source_kind'],'source_sha256':expected,
        'frames':480,'source_width':width,'source_height':height,
        'route_window_frames':len(region),'body_visible_frames':sum(region),
        'body_visible_fraction':round(sum(region)/len(region),6),
        'frame_measurements':measured,
        'first_native_frame':frames[0]['native_frame'],
        'last_native_frame':frames[-1]['native_frame'],
        'method':'vehicle instance mask >=4 pixels and absolute RGB Weber contrast >=0.05',
        'physical_behavior_confirmed':False,'accepted':False}
