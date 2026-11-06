"""Independent source-bound witness and cited-exception synthetic comparisons."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;NATIVE=HERE/'native';sys.path.insert(0,str(NATIVE))
import measure

def audit():
 plan=json.loads((HERE/'case-plan.json').read_text());comp=plan['comparisons']
 assert len(comp)==2
 assert comp[0]['deliberate_differences']==['crosswalk_pedestrian_yield']
 assert comp[1]['deliberate_differences']==['blind_white_cane_exception_applicability']
 pair={}
 for case in ('witness_1','witness_2','exception_1_1','exception_1_2'):
  path=NATIVE/'fixtures'/(case+'-480.json')
  pair[case]={'rows':json.loads(path.read_text())['frames'],'measurement':measure.measure(path,measure.sha256(path)),'sha256':measure.sha256(path)}
 a=pair['witness_1'];b=pair['witness_2'];e=pair['exception_1_1'];f=pair['exception_1_2']
 for x,y in zip(a['rows'],b['rows']):
  for key in ('frame','time_s','official_device_actors_present','crosswalk_marked','pedestrian_on_ego_highway_half','road_one_way','ego_directional_lanes','pedestrian_conflict_occupied','pedestrian_blind_declared','white_cane_declared'):assert x[key]==y[key]
 for x,y in zip(e['rows'],f['rows']):
  for key in ('frame','time_s','ego_x_m','ego_y_m','ego_speed_m_s','official_device_actors_present','crosswalk_marked','pedestrian_on_ego_highway_half','road_one_way','ego_directional_lanes','pedestrian_conflict_occupied'):assert x[key]==y[key]
 assert a['measurement']['yielded_to_crosswalk_pedestrian'] is True
 assert b['measurement']['yielded_to_crosswalk_pedestrian'] is False
 assert a['measurement']['first_ego_crosswalk_overlap_frame']==177
 assert b['measurement']['first_ego_crosswalk_overlap_frame']==137
 assert b['measurement']['ego_pedestrian_overlap_frames']==list(range(140,156))
 assert e['measurement']['blind_white_cane_exception_declared'] is False
 assert f['measurement']['blind_white_cane_exception_declared'] is True
 assert e['measurement']['yielded_to_crosswalk_pedestrian'] is f['measurement']['yielded_to_crosswalk_pedestrian'] is True
 assert not e['measurement']['blind_white_cane_physically_verified'] and not f['measurement']['blind_white_cane_physically_verified']
 packages=json.loads((HERE/'package-probes-summary.json').read_text())
 assert len(packages['results'])==16 and all(r['exit_code']==0 for r in packages['results'])
 return {'passed':True,'assignment_id':HERE.name,'candidate_bundles':16,
         'witness_yield':[True,False],'exception_declared':[False,True],
         'witness_source_hashes':[a['sha256'],b['sha256']],
         'exception_source_hashes':[e['sha256'],f['sha256']],
         'physical_white_cane_verified':False,
         'scope':'synthetic controlled comparisons only; no physical acceptance'}
if __name__=='__main__':print(json.dumps(audit(),indent=2))
