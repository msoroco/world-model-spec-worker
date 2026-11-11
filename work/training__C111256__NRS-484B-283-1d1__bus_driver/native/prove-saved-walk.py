"""Exercise C111256 saved raw measurement on two small synthetic source trees."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import shutil

from measure_walk import analyze

ROOT=Path(__file__).resolve().parents[3]
OUTPUT=ROOT/'.runtime-work'/'c111256-walk-measurement'


def write(folder,rows,mapping,geometry):
    if folder.exists():shutil.rmtree(folder)
    folder.mkdir(parents=True)
    (folder/'road_geometry.json').write_text(json.dumps(geometry)+'\n')
    (folder/'native_samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (folder/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in mapping))


def body(x,y,hx,hy):
    return [[x-hx,y-hy],[x+hx,y-hy],[x+hx,y+hy],[x-hx,y+hy]]


def source_pair(contrast):
    geometry={'cell_id':'C111256','walk_signal_id':620,
              'crosswalk_y_range_m':[-12.0,-10.0],
              'bus_lane_x_range_m':[0.0,3.5],
              'synthetic_diagnostic':True}
    rows=[];mapping=[]
    for i in range(480):
        ped_x=-5 if i<110 else (5 if i>160 else -5+10*(i-110)/50)
        bus_y=(-15 if i<200 else -11) if not contrast else (-15 if i<130 else -11)
        rows.append({'native_frame':100+i,'time_s':round(i*.05+.05,4),
                     'walk_signal_actor_id':620,'pedestrian_actor_id':720,'bus_actor_id':820,
                     'walk_signal_display_observed':'Walk','pedestrian_facing_signal':True,
                     'speed_provenance':'synthetic_native_sample',
                     'bus_speed_mps':0.0 if bus_y==-15 else 2.0,
                     'bus_body_xy_m':body(1.75,bus_y,1.0,1.0),
                     'pedestrian_body_xy_m':body(ped_x,-11,.2,.2)})
        mapping.append({'native_frame':100+i,'video_frame':i,
                        'time_s':round(i*.05+.05,4)})
    return rows,mapping,geometry


def run():
    results={}
    for suffix,contrast in (('reference',False),('contrast',True)):
        rows,mapping,geometry=source_pair(contrast)
        write(OUTPUT/suffix,rows,mapping,geometry)
        value=analyze(OUTPUT/suffix)
        if value['frames']!=480 or value['directed_pedestrian_conflict_frames']!=19 or value['simultaneous_conflict_frames']!=(19 if contrast else 0):
            raise ValueError('Controlled raw crossing result differs')
        results[suffix]=value
    base=source_pair(False);rejected=0
    for change in ('missing_geometry','false_speed','wrong_frame','missing_pedestrian_body','wrong_signal','duplicate_frame'):
        rows,mapping,geometry=copy.deepcopy(base)
        if change=='false_speed':rows[0]['speed_provenance']='native_measured'
        elif change=='wrong_frame':mapping[4]['native_frame']=999
        elif change=='missing_pedestrian_body':del rows[4]['pedestrian_body_xy_m']
        elif change=='wrong_signal':rows[3]['walk_signal_actor_id']=621
        elif change=='duplicate_frame':rows[4]['native_frame']=rows[3]['native_frame']
        folder=OUTPUT/'negative'/change;write(folder,rows,mapping,geometry)
        if change=='missing_geometry':(folder/'road_geometry.json').unlink()
        try:analyze(folder)
        except ValueError:rejected+=1
        else:raise ValueError('Damaged saved source accepted: '+change)
    return {'reference_simultaneous_frames':results['reference']['simultaneous_conflict_frames'],
            'contrast_simultaneous_frames':results['contrast']['simultaneous_conflict_frames'],
            'raw_frame_joins_checked':960,'source_sha256':{key:value['source_sha256'] for key,value in results.items()},
            'negative_rejections':rejected,'physical_acceptance_claimed':False,
            'legal_verdict_claimed':False}


if __name__=='__main__':
    print(json.dumps(run(),sort_keys=True))
