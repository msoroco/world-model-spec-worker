"""CPU emulation of the proposed original-source schema, never a CARLA claim."""
import copy
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from measure import synthetic,measure,sha
from runner_capture import original_row


def run():
    records=[]
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        road=root/'road.xodr';road.write_bytes((HERE/'native/road.xodr').read_bytes())
        for suffix in ('witness_1','witness_2'):
            original=synthetic(suffix,sha(road))
            original['source_kind']='synthetic_original_shape_emulation'
            for index,row in enumerate(original['frames']):
                bike=row['bicycle'];motor=row['motor_vehicle']
                b={**bike,'blueprint_id':'vehicle.bh.crossbike'}
                m={**motor,'blueprint_id':'vehicle.lincoln.mkz_2020'}
                built=original_row(index,index+100,b,m,motor['brake_applied'])
                for actor in ('bicycle','motor_vehicle'):
                    center=built[actor]['center_xy_m']
                    built[actor]['body_xy_m']=[[center[0]+1.05*(p[0]-center[0]),
                                               center[1]+1.05*(p[1]-center[1])]
                                              for p in built[actor]['body_xy_m']]
                original['frames'][index]=built
            path=root/(suffix+'.json');path.write_text(json.dumps(original)+'\n')
            result=measure(path,sha(path),road)
            assert result['frames']==480 and not result['human_propulsion_physically_verified']
            assert not result['physical_behavior_observed']
            changed=copy.deepcopy(original)
            changed['frames'][20]['bicycle']['blueprint_id']='vehicle.tesla.model3'
            path.write_text(json.dumps(changed)+'\n')
            try:measure(path,sha(path),road)
            except ValueError as error:assert 'blueprint source differs' in str(error)
            else:raise AssertionError('Wrong original bicycle blueprint accepted')
            changed=copy.deepcopy(original)
            changed['frames'][20]['native_frame']=changed['frames'][19]['native_frame']
            path.write_text(json.dumps(changed)+'\n')
            try:measure(path,sha(path),road)
            except ValueError as error:assert 'frame/time join differs' in str(error)
            else:raise AssertionError('Repeated original Native frame accepted')
            records.append({'case':suffix,'emulated_original_body_shape_passed':True,
                            'wrong_blueprint_rejected':True,'repeated_frame_rejected':True,
                            'human_propulsion_claimed':False})
    return {'passed':True,'records':records,'scope':'synthetic CPU schema emulation only'}


if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
