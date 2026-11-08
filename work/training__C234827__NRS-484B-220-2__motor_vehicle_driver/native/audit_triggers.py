"""Independently recompute rotary fallback metrics and replay negatives."""
import json
import math
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES,sha
from triggers import route

HERE=Path(__file__).resolve().parent


def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,values):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in values))


def audit():
    path=HERE/'trigger-proof.json';proof=json.loads(path.read_text())
    expected=['reference','contrast','entry-occluded','lane-deviation']
    mutations=['wrong_expected_hash','missing_camera_frame','wrong_island_readback']
    if (proof['format']!='c234827-measured-trigger-proof-v1' or
            proof['assignment_id']!=HERE.parent.name or
            proof['processor_sha256']!=sha(HERE/'triggers.py') or
            proof['saved_processor_sha256']!=sha(HERE/'measure_saved.py') or
            [item['variant'] for item in proof['positives']]!=expected or
            [item['mutation'] for item in proof['negative_controls']]!=mutations or
            not all(item['rejected'] is True for item in proof['negative_controls']) or
            proof['original_native_observed'] or
            proof['selected_candidate'] is not None or proof['delivery_ready']):
        raise ValueError('Rotary trigger proof provenance differs')
    checked=0
    for item in proof['positives']:
        name=item['variant']
        folder=(HERE/'saved-fixtures'/name if name in ('reference','contrast')
                else HERE/'trigger-fixtures'/name)
        hashes={file:sha(folder/file) for file in FILES}
        if hashes!=item['source_hashes']:
            raise ValueError('Rotary trigger source hashes differ')
        observed=load(folder/'native-observed.jsonl')
        frames=load(folder/'island-frames.jsonl')
        if len(observed)!=240 or len(frames)!=240:
            raise ValueError('Rotary trigger saved rows differ')
        entry_visible=0;max_deviation=0
        for i,(row,frame) in enumerate(zip(observed,frames)):
            if (row['frame']!=i or frame['frame']!=i or
                    row['native_frame']!=frame['camera_frame'] or
                    row['time_s']!=frame['time_s']):
                raise ValueError('Rotary trigger independent frame join differs')
            if i<40:entry_visible+=frame['island_visible']
            target=27.25 if row['lane_id']==-2 else 23.75
            max_deviation=max(max_deviation,abs(math.hypot(row['ego_x_m'],row['ego_y_m'])-target))
            checked+=1
        result=item['routing']
        if (result['measurements']['entry_visible_frames']!=entry_visible or
                result['measurements']['maximum_lane_center_deviation_m']!=round(max_deviation,3) or
                result['triggered']['fallback1_slow_for_entry_visibility']!=(entry_visible<20) or
                result['triggered']['fallback2_outer_lane_for_center_deviation']!=(round(max_deviation,3)>.2) or
                result['triggered']['fallback3_stop_for_unverified_island_or_control'] is not True or
                result['selected_candidate'] is not None or result['delivery_ready'] or
                route(folder,hashes)!=result):
            raise ValueError('Rotary trigger independent decision differs')
    replayed=[];source=HERE/'saved-fixtures'/'reference'
    for mutation in mutations:
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder=Path(temporary)/'saved';shutil.copytree(source,folder)
            if mutation=='missing_camera_frame':
                target=folder/'island-frames.jsonl';data=load(target);data.pop();write(target,data)
            elif mutation=='wrong_island_readback':
                target=folder/'island-readback.json';data=json.loads(target.read_text())
                data['center_xy_m']=[1,0];target.write_text(json.dumps(data)+'\n')
            hashes={file:sha(folder/file) for file in FILES}
            if mutation=='wrong_expected_hash':hashes['native-observed.jsonl']='0'*64
            try:route(folder,hashes if mutation=='wrong_expected_hash' else None)
            except (ValueError,TypeError):replayed.append(mutation)
            else:raise ValueError('Independent rotary trigger negative accepted')
    if checked!=960:raise ValueError('Rotary trigger coverage incomplete')
    receipt={'format':'c234827-independent-trigger-audit-v1',
        'proof_sha256':sha(path),'saved_rows_recomputed':checked,
        'negative_controls_replayed':replayed,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'trigger-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
