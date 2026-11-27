"""Independent original alley-width source, full video and pixel audit.

Diagnostic fixtures exercise the software path only. An actual Native attempt
requires every source PNG to match the complete lossless FFV1 camera video.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

from PIL import Image
from width_measurement import ASSIGNMENT,measure_saved

VIEWS=("overview","approach","reference_corner","driver_reference")


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    if path.is_symlink() or not path.is_file():raise ValueError('original source missing: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def decode(video):
    if video.is_symlink() or not video.is_file():raise ValueError('original camera video missing')
    probe=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=codec_name,width,height,nb_read_frames,avg_frame_rate',
        '-of','json',str(video)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout).get('streams',[])
    if len(streams)!=1 or streams[0].get('codec_name')!='ffv1':
        raise ValueError('original camera lossless FFV1 profile differs')
    count=int(streams[0].get('nb_read_frames',-1))
    if count<1:raise ValueError('original camera contains no frames')
    done=subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(video),
                         '-map','0:v:0','-f','null','-'],capture_output=True,text=True)
    if done.returncode:raise ValueError('original camera full decode failed: '+done.stderr[-300:])
    return {'sha256':sha(video),'decoded_frames':count,
            'dimensions':[int(streams[0]['width']),int(streams[0]['height'])],
            'fps':streams[0]['avg_frame_rate']}


def compare_every_original_pixel(video,archive,frames,dimensions):
    width,height=dimensions
    size=width*height*3
    command=['ffmpeg','-nostdin','-v','error','-xerror','-i',str(video),
             '-map','0:v:0','-pix_fmt','rgb24','-f','rawvideo','-']
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    checked=0
    try:
        with zipfile.ZipFile(archive) as source:
            expected=[f"{i:04d}-{row['frame']}.png" for i,row in enumerate(frames)]
            if source.namelist()!=expected:
                raise ValueError('original camera archive/frame order differs')
            for name in expected:
                decoded=process.stdout.read(size)
                if len(decoded)!=size:
                    raise ValueError('original camera decoded pixels incomplete')
                with Image.open(io.BytesIO(source.read(name))) as image:
                    if image.size!=(width,height) or image.convert('RGB').tobytes()!=decoded:
                        raise ValueError('original camera source/video pixels differ: '+name)
                checked+=1
            if process.stdout.read(1):
                raise ValueError('original camera has extra decoded pixels')
        if process.wait(timeout=180)!=0:
            raise ValueError('original camera pixel decoder failed')
        return checked
    finally:
        if process.poll() is None:process.kill();process.wait()
        if process.stdout:process.stdout.close()
        if process.stderr:process.stderr.close()


def audit(attempt,case_id,plan):
    attempt=Path(attempt)
    planned=json.loads(Path(plan).read_text())
    if not case_id.startswith(ASSIGNMENT+'__') or case_id not in {row['case_id'] for row in planned['cases']}:
        raise ValueError('exact alley-width delivery case differs')
    source=attempt/'original-attempt'
    inventory=json.loads((source/'inventory.json').read_text())
    diagnostic=inventory.get('diagnostic_fixture') is True
    count=9 if diagnostic else 900
    if not diagnostic and inventory.get('diagnostic_fixture') is not False:
        raise ValueError('original Native provenance missing')
    if inventory.get('case_id')!=case_id or inventory.get('frame_count')!=count:
        raise ValueError('original width inventory case/frame count differs')
    measured=measure_saved(source,case_id,expected_frames=count)
    mapped=rows(attempt/'video_frames.jsonl')
    trace=rows(attempt/'trace.jsonl')
    evidence=rows(attempt/'capture/evidence.jsonl')
    original=json.loads((source/'frame_map.json').read_text())['frames']
    if len(mapped)!=count or len(trace)!=count or len(evidence)!=count or len(original)!=count:
        raise ValueError('original alley-width video/Core/actor counts differ')
    for i,(video,src) in enumerate(zip(mapped,original)):
        if (video.get('video_frame')!=i or video.get('carla_frame')!=src['frame'] or
                video.get('time_s')!=src['time_s'] or trace[i].get('frame')!=src['frame'] or
                evidence[i].get('original_frame')!=src['frame']):
            raise ValueError('original alley-width video/Core/actor frame join differs')
    videos={view:decode(attempt/(view+'.mkv')) for view in VIEWS}
    if any(item['decoded_frames']!=count for item in videos.values()):
        raise ValueError('original alley-width full decode count differs')
    pixels={}
    if not diagnostic:
        seal=json.loads((attempt/'capture-seal.json').read_text())
        if seal.get('frames')!=900 or seal.get('diagnostic_fixture') is not False:
            raise ValueError('sealed original Native 900-frame capture required')
        for view in VIEWS:
            archive=source/(view+'.zip')
            ref=inventory.get('media',{}).get(view,{})
            if not archive.is_file() or ref.get('sha256')!=sha(archive):
                raise ValueError('original camera archive source changed: '+view)
            pixels[view]=compare_every_original_pixel(attempt/(view+'.mkv'),archive,
                original,videos[view]['dimensions'])
    return {'format':'c135705-independent-alley-width-delivery-audit-v1',
            'case_id':case_id,'source_inventory_sha256':sha(source/'inventory.json'),
            'source_measurement':measured['minimum_available_continuous_width_ft'],
            'capture_frames':count,'four_view_full_decode':videos,
            'original_pixel_verified_frames':pixels,
            'diagnostic_fixture':diagnostic,'actual_pixels_verified':not diagnostic,
            'physical_acceptance':False,'free_movement_judgment':'unresolved',
            'ordinance_judgment':'unresolved'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case-id',required=True)
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('refusing to replace independent audit')
    result=audit(args.attempt,args.case_id,args.plan)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':main()
