"""Exercise original-observation schema with explicitly synthetic in-memory controls."""
import json
from pathlib import Path
import tempfile

import measure_exit_saved

CASE=Path(__file__).resolve().parent.parent

def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write_rows(path,items):Path(path).write_text(''.join(json.dumps(x)+'\n' for x in items))

def prove():
    positives=[];negatives=[]
    for witness in ('witness_1','witness_2'):
        bundle=CASE/'offline'/'bundles'/witness/'primary'
        with tempfile.TemporaryDirectory() as temporary:
            saved=Path(temporary)
            source=bundle/'connected-saved';observed=rows(source/'native-observed.jsonl')
            cameras=rows(source/'camera-frames.jsonl')
            requests=rows(bundle/'connected-requested-tracks.jsonl')
            for row,request in zip(observed,requests):
                row['source_kind']='original_native';row['ego_actor_id']=131364
                row['ego_blueprint']='vehicle.tesla.model3'
                row['ego_heading_deg']=request['ego_heading_deg']
                row['ego_x_m']+=.02
                for point in row['ego_body_xy_m']:point[0]+=.02
                row['actual_exit_observed']=row['road_id']==12
            for frame in cameras:frame['source_kind']='original_native'
            readback=json.loads((source/'lane-readback.json').read_text())
            readback.update(source_kind='original_native',ego_actor_id=131364,
                native_map_sha256='0'*64,review_provenance='human_frame_review')
            write_rows(saved/'native-observed.jsonl',observed)
            write_rows(saved/'camera-frames.jsonl',cameras)
            (saved/'lane-readback.json').write_text(json.dumps(readback)+'\n')
            result=measure_exit_saved.measure(bundle,saved)
            if (not result['actual_left_exit_observed'] or result['delivery_ready'] or
                    result['observed_entry_to_exit_heading_change_deg']!=90):
                raise AssertionError('Original-schema synthetic control differs')
            positives.append({'witness':witness,'synthetic_original_schema_only':True,
                'observed_exit_frames':result['phase_frames']['exit'],
                'heading_change_deg':result['observed_entry_to_exit_heading_change_deg']})
            observed[100]['phase']='exit'
            write_rows(saved/'native-observed.jsonl',observed)
            try:measure_exit_saved.measure(bundle,saved)
            except ValueError:negatives.append({'witness':witness,'mutation':'observed_phase','rejected':True})
            else:raise AssertionError('Wrong observed phase accepted')
    proof={'format':'c131364-observed-schema-cpu-control-v1','positives':positives,
        'negatives':negatives,'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'proof-observed-schema.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':print(json.dumps(prove()))
