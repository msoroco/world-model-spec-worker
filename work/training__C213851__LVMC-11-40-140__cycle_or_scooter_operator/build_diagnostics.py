"""Generate textual source-bound sidewalk diagnostics; never physical evidence."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def video_hashes():
    stage = REPO/'.runtime-work/c213851-camera-hashes'
    stage.mkdir(parents=True, exist_ok=True)
    result = {}
    for name in VIEWS:
        path = stage/(name+'.mkv')
        if not path.exists():
            width, height = (1920,1080) if name == 'overview' else (1280,720)
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','lavfi','-i',f'color=c=black:s={width}x{height}:r=20',
                '-frames:v','600','-an','-c:v','ffv1','-threads','1',
                '-fflags','+bitexact','-flags:v','+bitexact',str(path)], check=True, timeout=120)
        result[name+'.mkv'] = sha(path)
    return result


def main():
    cameras = video_hashes()
    road = ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C213851-driveway" '
        'version="1" date="2026-11-25" north="8" south="-8" east="155" west="-5" '
        'vendor="full-train-worker"/><road id="1" name="driveway" length="150" junction="-1">'
        '<link/><planView><geometry s="0" x="-5" y="0" hdg="0" length="150"><line/>'
        '</geometry></planView><lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>'
        '<laneSection s="0"><left><lane id="1" type="sidewalk" level="false">'
        '<width sOffset="0" a="2" b="0" c="0" d="0"/></lane></left><center><lane id="0" '
        'type="none" level="false"/></center><right><lane id="-1" type="driving" '
        'level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/>'
        '</lane></right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>\n')
    lines = lambda data: ''.join(json.dumps(row, separators=(',',':'))+'\n' for row in data)
    for suffix in ('probe_01','probe_02'):
        cid = AID+'__'+suffix
        frames=[];native=[];trace=[];evidence=[];replay=[];graphs=[]
        for i in range(600):
            frame=100+i;t=round(i*.05,8)
            if suffix=='probe_01':
                x=(-10+i*.05 if i<180 else -1 if i<220 else (i-220)*.05)
                speed=0.0 if 180<=i<220 else 1.0
                ped_x=0.0 if 170<=i<210 else 3.0
            else:
                x=-10+i*.05
                speed=1.0
                ped_x=0.0 if 190<=i<210 else 3.0
            frames.append({'video_frame':i,'carla_frame':frame,'native_frame':frame,'time_s':t})
            native.append({'source_kind':'synthetic_native_sample','frame':i,'native_frame':frame,
                't_s':t,'rider_id':1,'pedestrian_id':2,'rider_x_m':x,'rider_y_m':0.0,
                'rider_speed_mps':speed,'pedestrian_x_m':ped_x,'pedestrian_y_m':0.0,
                'requested_stop_phase':suffix=='probe_01' and 180<=i<260})
            trace.append({'frame':frame,'time_s':t,'position':{'x':x,'y':0.0,'z':0},
                'position_m':[x,0.0,0],'heading_deg':0,'speed_mps':speed,
                'speed_mph':speed/.44704,'velocity_mps':[speed,0,0],'control':{}})
            bbox=[[x+dx,dy,z] for dx in (-.3,.3) for dy in (-.2,.2) for z in (0,1.2)]
            graph=f'graphs/base/{frame:08d}.adapter.json'
            evidence.append({'original_frame':frame,'replay_frame':frame,'actor_id':1,
                'recording_time_s':t,'replay_simulation_time_s':t,
                'ego':{'position_m':[x,0,0],'heading_deg':0,'speed_mps':speed,
                    'speed_provenance':'synthetic_native_sample','body_vertices_m':bbox},
                'synthetic_diagnostic':True,
                'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0}}})
            replay.append({'frame':frame,'time_s':t,'simulation_time':t,
                'synthetic_diagnostic':True,'adapter_graph':graph})
            graphs.append({'path':'capture/native/'+graph,'attributes':{
                'frame':frame,'simulation_time_s':t,'synthetic_diagnostic':True,
                'source':'C213851 sidewalk crossing software diagnostic'},
                'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':1,
                'vertex':[x,0,0],'forward':[1,0,0],'threedbbox':bbox}}],'edges':[]})
        trace_text=lines(trace)
        capture_manifest={'extraction_confirmed':True,'frames':600,'required_observations':[],
            'sources':{'trace.jsonl':hashlib.sha256(trace_text.encode()).hexdigest(),
                'road.xodr':hashlib.sha256(road.encode()).hexdigest()},
            'synthetic_diagnostic':True}
        context={'assignment_id':AID,'case_id':cid,'source_kind':'synthetic_native_sample',
            'district':'residence','district_source_id':'synthetic-fixture:district',
            'origin_kind':'driveway','origin_source_id':'synthetic-fixture:driveway',
            'travel_direction':'into_driveway',
            'sidewalk_continuation_across_origin':True,
            'sidewalk_continuation_source_id':'synthetic-fixture:sidewalk-continuation',
            'sidewalk_boundary_source_id':'synthetic-fixture:boundary',
            'rider_class':'bicycle','rider_class_source_id':'synthetic-fixture:blueprint',
            'pedestrian_conflict_source_id':'synthetic-fixture:conflict-polygon',
            'sidewalk_boundary_point_xyz_m':[0,0,0],
            'sidewalk_approach_direction_xyz':[1,0,0],
            'pedestrian_conflict_polygon_xy_m':[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]],
            'camera_sha256':cameras,'review_kind':'synthetic_diagnostic',
            'reviewer':'synthetic-software-test'}
        context['sidewalk_context']={'source_kind':'synthetic_diagnostic',
            'district':'residence','origin_kind':'driveway',
            'travel_direction':'into_driveway',
            'sidewalk_continuation_across_origin':True}
        spec={'files':{'video_frames.jsonl':lines(frames),
            'sidewalk-native.jsonl':lines(native), 'sidewalk_context.json':json.dumps(context)+'\n',
            'trace.jsonl':trace_text,'road.xodr':road,
            'capture/evidence.jsonl':lines(evidence),
            'capture/native/frames.jsonl':lines(replay),
            'capture/recorder_info.txt':'Create 1: vehicle.bh.crossbike (0) at (-10, 0, 0)\n',
            'capture/manifest.json':json.dumps(capture_manifest,separators=(',',':'))+'\n'},
            'graphs':graphs,
            'videos':[{'path':name+'.mkv','frames':600,
                'width':1920 if name=='overview' else 1280,
                'height':1080 if name=='overview' else 720,'fps':20,'color':'black'}
                for name in VIEWS]}
        path=HERE/'cases'/suffix/'diagnostic.json'
        write(path,spec)
        relative=str(path.relative_to(REPO))
        recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':sha(path)}],
            'generator':{'source':relative,'sha256':sha(path)}}
        write(path.parent/'recipe.json',recipe)
        print(json.dumps({'case':cid,'diagnostic_sha256':sha(path)},sort_keys=True))


if __name__=='__main__':
    main()
