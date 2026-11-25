"""Build two controlled diagnostic variants from the exact dry bundle.

These packets are synthetic and cannot pass the Native review guard.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=json.loads((ROOT/'construction.json').read_text())
VARIANTS={
 'wet_same_traffic':{'surface':'wet','weather':(80,80,80,10,100,20),
                     'target':{'surface':'wet','lane_width_m':[3,4],
                               'longitudinal_body_gap_m':[10,35],
                               'sight_distance_m':[50,120],
                               'precipitation_percent':[70,90]},
                     'lead_spawn_x':25,'lead_target_speed_mps':7},
 'dense_traffic':{'surface':'dry','weather':(10,0,0,0,100,30),
                  'target':{'surface':'dry','lane_width_m':[3,4],
                            'longitudinal_body_gap_m':[4,12],
                            'sight_distance_m':[50,120],
                            'precipitation_percent':[0,5]},
                  'lead_spawn_x':15,'lead_target_speed_mps':4},
}


def build(suffix, variant):
    files={row['path']:row['content'] for row in BASE['files']}
    config=json.loads(files['config.json'])
    case=config['selected_case_id'].rsplit('__',1)[0]+'__'+suffix
    config['selected_case_id']=case
    config['condition_target']=variant['target']
    files['config.json']=json.dumps(config,indent=2)+'\n'
    source=(files['surface.txt'] if suffix=='dense_traffic' else
            f'Synthetic {suffix} surface planning note; no original Native site review.\n')
    files['surface.txt']=source
    surface=json.loads(files['surface_packet.json'])
    surface['surface']=variant['surface']
    surface['source']['sha256']=hashlib.sha256(source.encode()).hexdigest()
    files['surface_packet.json']=json.dumps(surface,indent=2)+'\n'
    weather=dict(zip(('cloudiness','precipitation','wetness','fog_density',
                      'fog_distance','sun_altitude_angle'),variant['weather']))
    weather_doc=json.dumps({'native_map_id':'TownX','weather_profile':weather,
                            'status':'synthetic diagnostic'},indent=2)+'\n'
    files['weather.json']=weather_doc
    road=json.loads(files['road_packet.json'])
    road['case_id']=case
    road['lead_spawn']['x']=variant['lead_spawn_x']
    road['lead_target_speed_mps']=variant['lead_target_speed_mps']
    road['weather_profile']=weather
    road['weather_profile_source']['sha256']=hashlib.sha256(weather_doc.encode()).hexdigest()
    files['road_packet.json']=json.dumps(road,indent=2)+'\n'
    package=dict(BASE,case_id=case)
    package['files']=[{'path':row['path'],'content':files[row['path']]} for row in BASE['files']]
    package['mechanisms']=dict(BASE['mechanisms'],
                               controlled_change='wet surface/weather' if suffix.startswith('wet') else 'lead speed/body gap')
    path=ROOT/'cases'/(suffix+'-construction.json')
    path.write_text(json.dumps(package,indent=2)+'\n')
    return {'case_id':case,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__=='__main__':
    print(json.dumps([build(suffix,variant) for suffix,variant in VARIANTS.items()],indent=2))
