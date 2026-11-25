"""Check controlled construction differences in three selected C179789 cases."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def files(name):
    path=ROOT/('construction.json' if name=='dry' else 'cases/'+name+'-construction.json')
    package=json.loads(path.read_text())
    return package,{row['path']:row['content'] for row in package['files']}


def check():
    dry,d=files('dry')
    wet,w=files('wet_same_traffic')
    dense,t=files('dense_traffic')
    for package,bundle in ((wet,w),(dense,t)):
        if set(bundle)!=set(d) or package['recording_description']!=dry['recording_description']:
            raise ValueError('Controlled source/camera inventory differs')
        for name in ('runner.py','camera_setup.py','camera_encoder.py',
                     'condition_capture.py','condition_construction.py',
                     'traffic_construction.py','traffic_controller.py',
                     'conditions_measurements.py','finalizer.py','delivery_audit.py',
                     'measurement-contract.json'):
            if bundle[name]!=d[name]:
                raise ValueError('Shared construction implementation differs: '+name)
    dc,wc,tc=[json.loads(bundle['config.json']) for bundle in (d,w,t)]
    for other in (wc,tc):
        shared={key:value for key,value in other.items() if key not in ('selected_case_id','condition_target')}
        baseline={key:value for key,value in dc.items() if key not in ('selected_case_id','condition_target')}
        if shared!=baseline:
            raise ValueError('Fixed case capture contract differs')
    dr,wr,tr=[json.loads(bundle['road_packet.json']) for bundle in (d,w,t)]
    for key in ('native_map_id','road_id','lane_id','ego_spawn','vehicle_blueprint_id',
                'lead_blueprint_id','ego_target_speed_mps','surface_packet'):
        if not dr[key]==wr[key]==tr[key]:
            raise ValueError('Fixed road/ego construction differs: '+key)
    for key in ('lead_spawn','lead_target_speed_mps'):
        if wr[key]!=dr[key] or tr[key]==dr[key]:
            raise ValueError('Traffic comparison variable differs: '+key)
    if (wc['condition_target']['surface']!='wet' or tc['condition_target']['surface']!='dry'
            or dc['condition_target']['surface']!='dry'):
        raise ValueError('Surface comparison cases differ')
    if tr['weather_profile']!=dr['weather_profile'] or wr['weather_profile']==dr['weather_profile']:
        raise ValueError('Weather comparison variable differs')
    if d['surface.txt']!=t['surface.txt'] or d['weather.json']!=t['weather.json']:
        raise ValueError('Dense traffic changed fixed surface/weather source')
    if d['surface.txt']==w['surface.txt'] or d['weather.json']==w['weather.json']:
        raise ValueError('Wet case lacks distinct condition source')
    return {'format':'worker-c179789-construction-comparison','passed':True,
            'cases':[package['case_id'] for package in (dry,wet,dense)],
            'fixed':['runner','four cameras','road identity','ego spawn','capture contract'],
            'wet_difference':['surface source','weather profile'],
            'dense_difference':['lead spawn gap','lead speed'],
            'physical_realization_verified':False}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
