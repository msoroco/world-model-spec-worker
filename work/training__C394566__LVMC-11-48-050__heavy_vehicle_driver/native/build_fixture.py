"""Create small, explicitly synthetic route-source diagnostics for two exact cases."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
AID = FOLDER.name
SOURCE = ROOT/'work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/diagnostic-probe_01.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    original=json.loads(SOURCE.read_text())
    source_files=original['files']
    for suffix,truck_route in (('truck_route',True),('non_truck_route',False)):
        case=AID+'__'+suffix
        files={name:value for name,value in source_files.items() if name not in ('native_route_trace.jsonl','route_context.json')}
        files['capture/manifest.json']=files['capture/manifest.json'].replace(
            'training__C394566__LVMC-11-48-060__motor_vehicle_driver__probe_01',case)
        rows=[]
        maps=[json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
        for line,frame in zip(source_files['native_route_trace.jsonl'].splitlines(),maps):
            row=json.loads(line)
            row.update(case_id=case,source_kind='original_native_pose',time_s=frame['time_s'],
                       vehicle_half_extent_m=[3.0,1.2])
            rows.append(json.dumps(row,separators=(',',':')))
        assert len(rows)==600
        files['original-route-rows.jsonl']='\n'.join(rows)+'\n'
        facts={'unladen_weight_lb':8001,'district':'residence','truck_route':truck_route,
               'civil_timestamp':'2026-11-27T20:00:00-08:00','written_permit_status':'absent'}
        refs={}
        for name in ('weight','district','truck_route','civil_clock','permit'):
            path=name+'.source.json'
            text=json.dumps({'source_kind':'synthetic_diagnostic','fact':name,
                'requested_value': facts.get(name if name not in ('civil_clock','permit') else
                                             ('civil_timestamp' if name=='civil_clock' else 'written_permit_status'))},sort_keys=True)+'\n'
            files[path]=text
            refs[name]={'path':path,'sha256':hashlib.sha256(text.encode()).hexdigest()}
        context={'case_id':case,'source_kind':'synthetic_native_sample',
                 'authority_refs':refs,'facts':facts,'legal_verdict':None}
        context.update({'ru.truck': {'source_kind': 'synthetic_diagnostic', 'vehicle_class': 'truck'},
                        'ru.commercial_motor_vehicle': {'source_kind': 'synthetic_diagnostic', 'vehicle_class': 'heavy_vehicle'},
                        'kin.extent': {'source_kind': 'synthetic_diagnostic', 'half_extent_m': [3.0,1.2], 'certified_weight_separate': True},
                        'st.roadway': {'source_kind': 'synthetic_diagnostic', 'road_id': rows[0] and json.loads(rows[0])['road_id']},
                        'dev.regulatory_sign': {'source_kind': 'synthetic_diagnostic', 'truck_route_designation': truck_route, 'authority_separate': True},
                        'env.civil_time': {'source_kind': 'synthetic_diagnostic', 'timestamp': facts['civil_timestamp']},
                        'drv.condition_in_effect': {'source_kind': 'synthetic_diagnostic', 'clock_window_review_required': True},
                        'kin.velocity': {'source_kind': 'synthetic_diagnostic', 'route_trace_required': True}})
        files['authority-context.json']=json.dumps(context,sort_keys=True)+'\n'
        names=('authority-context.json','original-route-rows.jsonl','video_frames.jsonl')
        seal={'case_id':case,'sha256':{name:hashlib.sha256(files[name].encode()).hexdigest() for name in names},
              'physical_or_legal_accepted':False}
        files['capture-seal.json']=json.dumps(seal,sort_keys=True)+'\n'
        spec={'files':files,'graphs':original['graphs'],'videos':original['videos']}
        out=FOLDER/f'diagnostic-{suffix}.json';out.write_text(json.dumps(spec,separators=(',',':'))+'\n')
        assignment=ROOT/'inputs'/AID/'assignment.json'
        recipe={'format':'worker-fixture-recipe','sources':[{'path':'fixture-assignment.json',
                'source':str(assignment.relative_to(ROOT)),'sha256':sha(assignment)}],
                'generator':{'source':str(out.relative_to(ROOT)),'sha256':sha(out)}}
        (FOLDER/f'fixture-recipe-{suffix}.json').write_text(json.dumps(recipe,indent=2)+'\n')
        print(suffix,out.stat().st_size)


if __name__=='__main__':
    build()
