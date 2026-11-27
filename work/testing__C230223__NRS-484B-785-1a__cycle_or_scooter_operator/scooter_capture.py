"""Capture 900 source-sealed Native scooter body/speed samples and four videos."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from package_spec import AID,CAMERA_NAMES
from scooter_785 import measure_original,need


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path,value):
    Path(path).write_text(json.dumps(value,sort_keys=True)+'\n')


def capture(adapter,site,case_id,destination):
    destination=Path(destination).resolve()
    need(destination.is_dir() and (destination/'construction.json').is_file() and
         'work' not in destination.parts and
         'runtime' not in destination.parts,
         'original Native attempt must be a materialized acquisition directory')
    need(getattr(adapter,'native_attested',False) is True,
         'attested original Native scooter adapter required')
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='scooter-original-',dir=destination.parent))
    try:
        adapter.configure()
        adapter.spawn()
        folders={name:stage/('frames-'+name) for name in CAMERA_NAMES}
        for folder in folders.values():
            folder.mkdir()
        rows,mapping,trace=[],[],[]
        prior=None
        for index in range(900):
            frame,time_s=adapter.tick()
            need(type(frame) is int and type(time_s) in (float,int),
                 'original Native scooter frame/time missing')
            if prior is not None:
                need(frame==prior[0]+1 and abs(time_s-prior[1]-.05)<=.002,
                     'original Native scooter 20 Hz cadence differs')
            prior=(frame,time_s)
            row=adapter.read(frame,time_s)
            need(row.get('frame')==frame and row.get('time_s')==time_s and
                 row.get('native_actor_id')==str(adapter.ego.id),
                 'original Native scooter actor/frame missing')
            row['native_frame']=frame
            row['original_frame']=frame
            row['frame']=index
            row['time_s']=index/20
            images=adapter.pixels(frame)
            need(set(images)==set(CAMERA_NAMES),'four original camera streams required')
            pixels={}
            for name in CAMERA_NAMES:
                image=images[name]
                raw=image.get('png')
                need(image.get('frame')==frame and isinstance(raw,bytes) and
                     raw.startswith(b'\x89PNG\r\n\x1a\n'),
                     'original scooter pixels missing: '+name)
                (folders[name]/f'{index:04d}.png').write_bytes(raw)
                pixels[name]=hashlib.sha256(raw).hexdigest()
            rows.append(row)
            mapping.append({'video_frame':index,'carla_frame':frame,
                            'native_frame':frame,'time_s':index/20,
                            'camera_png_sha256':pixels})
            position=row['position_xyz_m']
            trace.append({'frame':frame,'time_s':index/20,
                          'position_m':position,
                          'position':dict(zip(('x','y','z'),position)),
                          'heading_deg':row['heading_deg'],
                          'speed_mps':row['speed_mps'],
                          'speed_mph':row['speed_mps']/.44704})
        (stage/'video_frames.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in mapping))
        (stage/'trace.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in trace))
        history={'source_kind':'original_native_actor_history',
                 'assignment_id':AID,'case_id':case_id,
                 'reviewed_site_sha256':site['reviewed_site_sha256'],
                 'map_sha256':site['map_sha256'],
                 'scene':site['scene'],
                 'native_actor_id':rows[0]['native_actor_id'],
                 'samples':rows}
        put(stage/'scooter-history.json',history)
        try:
            put(stage/'scooter-measurement.json',
                measure_original(rows,site['scene'],adapter.case))
        except ValueError as error:
            put(stage/'scooter-measurement.json',
                {'measured':False,'physical_gap':str(error),
                 'ordinance_effect_judgment':None,'legal_verdict':None})
        videos={}
        for name,folder in folders.items():
            target=stage/(name+'.mkv')
            subprocess.run(['ffmpeg','-v','error','-nostdin','-framerate','20',
                            '-i',str(folder/'%04d.png'),'-frames:v','900',
                            '-c:v','ffv1',str(target)],check=True,
                           stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            videos[name]={'path':target.name,'sha256':sha(target),'frame_count':900}
            shutil.rmtree(folder)
        put(stage/'original-source-receipt.json',{
            'source_kind':'original_native_capture','diagnostic_fixture':False,
            'case_id':case_id,'fps':20,'frame_count':900,
            'reviewed_site_sha256':site['reviewed_site_sha256'],
            'history_sha256':sha(stage/'scooter-history.json'),
            'trace_sha256':sha(stage/'trace.jsonl'),
            'frame_map_sha256':sha(stage/'video_frames.jsonl'),
            'measurement_sha256':sha(stage/'scooter-measurement.json'),
            'cameras':videos,'physical_acceptance':False,
            'ordinance_effect_judgment':None,'legal_verdict':None})
        for source in stage.iterdir():
            target=destination/source.name
            need(not target.exists(),'original Native acquisition source already exists: '+source.name)
            os.replace(source,target)
        stage.rmdir()
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True)
        raise
    finally:
        adapter.cleanup()
