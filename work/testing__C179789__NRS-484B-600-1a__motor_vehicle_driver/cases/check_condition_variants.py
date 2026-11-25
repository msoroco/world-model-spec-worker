"""Check controlled construction differences in six selected C179789 cases."""
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
    narrow,n=files('narrow_same_traffic')
    low,l=files('low_visibility')
    ice,i=files('ice_or_snow')
    for package,bundle in ((wet,w),(dense,t),(narrow,n),(low,l),(ice,i)):
        if set(bundle)!=set(d) or package['recording_description']!=dry['recording_description']:
            raise ValueError('Controlled source/camera inventory differs')
        for name in ('runner.py','camera_setup.py','camera_encoder.py',
                     'condition_capture.py','condition_construction.py',
                     'traffic_construction.py','traffic_controller.py',
                     'conditions_measurements.py','finalizer.py','delivery_audit.py',
                     'measurement-contract.json'):
            if bundle[name]!=d[name]:
                raise ValueError('Shared construction implementation differs: '+name)
    dc,wc,tc,nc,lc,ic=[json.loads(bundle['config.json']) for bundle in (d,w,t,n,l,i)]
    for other in (wc,tc,nc,lc,ic):
        shared={key:value for key,value in other.items() if key not in ('selected_case_id','condition_target')}
        baseline={key:value for key,value in dc.items() if key not in ('selected_case_id','condition_target')}
        if shared!=baseline:
            raise ValueError('Fixed case capture contract differs')
    dr,wr,tr,nr,lr,ir=[json.loads(bundle['road_packet.json']) for bundle in (d,w,t,n,l,i)]
    for key in ('native_map_id','road_id','lane_id','ego_spawn','vehicle_blueprint_id',
                'lead_blueprint_id','ego_target_speed_mps','surface_packet'):
        if not dr[key]==wr[key]==tr[key]:
            raise ValueError('Fixed road/ego construction differs: '+key)
    for key in ('native_map_id','lane_id','vehicle_blueprint_id','lead_blueprint_id',
                'ego_target_speed_mps','surface_packet'):
        if nr[key]!=dr[key]:
            raise ValueError('Narrow case changed fixed vehicle/control: '+key)
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
    for key in ('native_map_id','road_id','lane_id','ego_spawn','lead_spawn',
                'vehicle_blueprint_id','lead_blueprint_id','ego_target_speed_mps',
                'lead_target_speed_mps','surface_packet'):
        if lr[key]!=dr[key]:
            raise ValueError('Low-visibility case changed fixed road or traffic: '+key)
    if l['surface.txt']!=d['surface.txt'] or l['weather.json']==d['weather.json']:
        raise ValueError('Low-visibility case changed surface or lacks weather source')
    for key in ('cloudiness','precipitation','wetness','sun_altitude_angle'):
        if lr['weather_profile'][key]!=dr['weather_profile'][key]:
            raise ValueError('Low-visibility case changed fixed weather: '+key)
    if (lr['weather_profile']['fog_density']!=80 or
            lr['weather_profile']['fog_distance']!=20 or
            lc['condition_target']['fog_density_percent']!=[70,90] or
            lc['condition_target']['fog_distance_m']!=[10,30]):
        raise ValueError('Low-visibility case lacks fog profile/readback target')
    for key in dc['condition_target']:
        if lc['condition_target'][key]!=dc['condition_target'][key]:
            raise ValueError('Low-visibility case changed fixed target: '+key)
    for key in ('native_map_id','road_id','lane_id','ego_spawn','lead_spawn',
                'vehicle_blueprint_id','lead_blueprint_id','ego_target_speed_mps',
                'lead_target_speed_mps','surface_packet'):
        if ir[key]!=dr[key]:
            raise ValueError('Ice/snow case changed fixed road or traffic: '+key)
    if (ir['weather_profile']==dr['weather_profile'] or i['surface.txt']==d['surface.txt']
            or ic['condition_target']['surface']!='ice_or_snow'
            or ic['condition_target']['precipitation_percent']!=[70,90]):
        raise ValueError('Ice/snow case lacks sourced condition change')
    ice_surface=json.loads(i['surface_packet.json'])
    if ice_surface['surface']!='ice_or_snow' or ice_surface['road_id']!=ir['road_id']:
        raise ValueError('Ice/snow source packet mismatches road')
    for key in ('lane_width_m','longitudinal_body_gap_m','sight_distance_m'):
        if ic['condition_target'][key]!=dc['condition_target'][key]:
            raise ValueError('Ice/snow case changed fixed target: '+key)
    for key in ('lead_target_speed_mps','weather_profile'):
        if nr[key]!=dr[key]:
            raise ValueError('Narrow case changed fixed traffic/weather: '+key)
    def gap(packet):
        return [packet['lead_spawn'][axis]-packet['ego_spawn'][axis] for axis in ('x','y','z')]
    if gap(nr)!=gap(dr) or nr['road_id']==dr['road_id'] or nr['ego_spawn']==dr['ego_spawn']:
        raise ValueError('Narrow site or fixed relative traffic differs')
    ns,ds=[json.loads(bundle['surface_packet.json']) for bundle in (n,d)]
    if (ns['surface']!='dry' or ns['road_id']!=nr['road_id'] or
            ds['surface']!='dry' or n['weather.json']!=d['weather.json']):
        raise ValueError('Narrow site surface/weather category differs')
    if (nc['condition_target']['lane_width_m']!=[2.5,2.9] or
            dc['condition_target']['lane_width_m']!=[3,4] or
            nc['condition_target']['surface']!='dry'):
        raise ValueError('Narrow case lacks exact width comparison target')
    return {'format':'worker-c179789-construction-comparison','passed':True,
            'cases':[package['case_id'] for package in (dry,wet,dense,narrow,low,ice)],
            'fixed':['runner','four cameras','capture contract',
                     'road identity and ego spawn for dry/wet/dense',
                     'vehicle/control/weather/surface category/relative traffic for narrow'],
            'wet_difference':['surface source','weather profile'],
            'dense_difference':['lead spawn gap','lead speed'],
            'narrow_difference':['separately reviewed road site',
                                 'Native route width survey and target interval'],
            'low_visibility_difference':['Native fog density and distance profile',
                                         'frame-specific weather readback target'],
            'ice_or_snow_difference':['separate ice/snow roadway source review',
                                      'Native precipitation and wetness profile'],
            'physical_realization_verified':False}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
