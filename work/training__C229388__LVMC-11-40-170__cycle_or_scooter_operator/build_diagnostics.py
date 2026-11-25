"""Build source-hashed textual parking diagnostics, never physical evidence."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def video_hashes():
    stage = REPO/'.runtime-work/c229388-camera-hashes'
    stage.mkdir(parents=True, exist_ok=True)
    out = {}
    for name in VIEWS:
        path = stage/(name+'.mkv')
        if not path.exists():
            width, height = (1920,1080) if name == 'overview' else (1280,720)
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','lavfi','-i',f'color=c=black:s={width}x{height}:r=20',
                '-frames:v','600','-an','-c:v','ffv1','-threads','1',
                '-fflags','+bitexact','-flags:v','+bitexact',str(path)],check=True,timeout=120)
        out[name+'.mkv'] = sha(path)
    return out


def main():
    camera_hash = video_hashes()
    road = ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C229388-rack-parking" '
        'version="1" date="2026-11-25" north="8" south="-8" east="155" west="-5" '
        'vendor="full-train-worker"/><road id="1" name="route" length="150" junction="-1">'
        '<link/><planView><geometry s="0" x="-5" y="0" hdg="0" length="150"><line/>'
        '</geometry></planView><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>'
        '<laneSection s="0"><left><lane id="1" type="biking" level="false">'
        '<width sOffset="0" a="2" b="0" c="0" d="0"/></lane></left><center><lane id="0" '
        'type="none" level="false"/></center><right><lane id="-1" type="driving" '
        'level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/>'
        '</lane></right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>\n')
    for suffix, y in (('probe_01',1.5),('probe_02',.9)):
        case = AID+'__'+suffix
        frames=[];native=[];trace=[];evidence=[];replay=[];graphs=[]
        for i in range(600):
            frame=100+i;t=round(i*.05,8);x=0.0
            left,right=x-.3,x+.3
            footprint=[[left,y-.2],[right,y-.2],[right,y+.2],[left,y+.2]]
            cx=(min(p[0] for p in footprint)+max(p[0] for p in footprint))/2
            cy=(min(p[1] for p in footprint)+max(p[1] for p in footprint))/2
            frames.append({'video_frame':i,'carla_frame':frame,'native_frame':frame,'time_s':t})
            native.append({'video_frame':i,'native_frame':frame,'source_kind':'synthetic_native_sample',
                'device_actor_id':1,'operator_actor_id':2,'device_speed_mps':0.0,
                'device_footprint_xy_m':footprint})
            trace.append({'frame':frame,'time_s':t,'position':{'x':cx,'y':cy,'z':0},
                'position_m':[cx,cy,0],'heading_deg':0,'speed_mps':0.0,
                'speed_mph':0.0,'velocity_mps':[0.0,0,0],'control':{}})
            bbox=[[cx+dx,cy+dy,z] for dx in (-.3,.3) for dy in (-.2,.2) for z in (0,1.2)]
            graph=f'graphs/base/{frame:08d}.adapter.json'
            evidence.append({'original_frame':frame,'replay_frame':frame,'actor_id':1,
                'recording_time_s':t,'replay_simulation_time_s':t,'ego':{'position_m':[cx,cy,0],
                'heading_deg':0,'speed_mps':0.0,'speed_provenance':'synthetic_native_sample',
                'body_vertices_m':bbox},'synthetic_diagnostic':True,
                'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0}}})
            replay.append({'frame':frame,'time_s':t,'simulation_time':t,
                'synthetic_diagnostic':True,'adapter_graph':graph})
            graphs.append({'path':'capture/native/'+graph,'attributes':{
                'frame':frame,'simulation_time_s':t,'synthetic_diagnostic':True,
                'source':'C229388 rack-parking software diagnostic'},
                'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':1,
                'vertex':[cx,cy,0],'forward':[1,0,0],'threedbbox':bbox}}],'edges':[]})
        lines=lambda rows: ''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows)
        trace_text=lines(trace)
        manifest={'extraction_confirmed':True,'frames':600,'required_observations':[],
            'sources':{'trace.jsonl':hashlib.sha256(trace_text.encode()).hexdigest(),
                       'road.xodr':hashlib.sha256(road.encode()).hexdigest()},
            'synthetic_diagnostic':True}
        context={'assignment_id':AID,'case_id':case,'review_kind':'synthetic_diagnostic',
            'camera_sha256':camera_hash,'reviewer':'synthetic-software-test',
            'device_subtype':'electric_scooter','device_actor_id':1,'operator_actor_id':2,
            'rack_actor_id':3,'rack_support_confirmed':True,
            'sidewalk_polygon_xy_m':[[-5,-3],[5,-3],[5,3],[-5,3]],
            'roadway_polygon_xy_m':[[-5,-7],[5,-7],[5,-3],[-5,-3]],
            'curb_polyline_xy_m':[[-5,-3],[5,-3]],
            'rack_polygon_xy_m':[[-1,1],[1,1],[1,2],[-1,2]],
            'pedestrian_corridor_polygon_xy_m':[[-5,-1],[5,-1],[5,1],[-5,1]]}
        context['parking_context']={'placement':'sidewalk_rack','source_kind':'synthetic_diagnostic'}
        for key in ('device_subtype_source','rack_support_source','sidewalk_geometry_source',
                    'roadway_geometry_source','curb_geometry_source','pedestrian_corridor_source',
                    'operator_join_source','parking_state_source'):
            context[key]='synthetic-fixture:'+key
        spec={'files':{'video_frames.jsonl':lines(frames),
                       'native_parking_trace.jsonl':lines(native),
                       'parking_context.json':json.dumps(context)+'\n',
                       'trace.jsonl':trace_text,'road.xodr':road,
                       'capture/evidence.jsonl':lines(evidence),
                       'capture/native/frames.jsonl':lines(replay),
                       'capture/recorder_info.txt':'Create 1: vehicle.scooter (0) at (0, 0, 0)\n',
                       'capture/manifest.json':json.dumps(manifest,separators=(',',':'))+'\n'},
              'graphs':graphs,'videos':[{'path':name+'.mkv','frames':600,
                  'width':1920 if name=='overview' else 1280,
                  'height':1080 if name=='overview' else 720,'fps':20,'color':'black'} for name in VIEWS]}
        path=HERE/'cases'/suffix/'diagnostic.json'
        write(path,spec)
        relative=str(path.relative_to(REPO))
        recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':sha(path)}],
            'generator':{'source':relative,'sha256':sha(path)}}
        write(path.parent/'recipe.json',recipe)
        print(json.dumps({'case':case,'diagnostic_sha256':sha(path)},sort_keys=True))


if __name__=='__main__':
    main()
