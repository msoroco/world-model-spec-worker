"""Independent 480-row one-way saved measurement and negative-control audit."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES, measure

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,rows):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def audit():
    proof_path=HERE/'saved-proof.json';proof=json.loads(proof_path.read_text())
    if (proof['format']!='c150916-saved-one-way-proof-v1' or
            proof['assignment_id']!=HERE.parent.name or
            proof['processor_sha256']!=sha(HERE/'measure_saved.py') or
            proof['original_native_observed'] or proof['delivery_ready'] or
            proof['legal_verdict'] is not None or len(proof['positives'])!=2 or
            [item['mutation'] for item in proof['negative_controls']]!=[
                'wrong_expected_hash','missing_saved_frame','wrong_velocity',
                'missing_sign_frame','wrong_designation_direction'] or
            not all(item['rejected'] is True for item in proof['negative_controls'])):
        raise ValueError('Saved one-way proof provenance or coverage differs')
    seen=set();rows_checked=0
    for item in proof['positives']:
        case=item['case']
        if case not in ('designated','opposite') or case in seen:
            raise ValueError('Saved one-way case coverage differs')
        seen.add(case)
        folder=HERE/'saved-fixtures'/case
        hashes={name:sha(folder/name) for name in FILES}
        if item['source_hashes']!=hashes or item['measurement']['source_hashes']!=hashes:
            raise ValueError('Saved one-way source hashes differ')
        observations=load(folder/'native-observed.jsonl')
        signs=load(folder/'sign-frames.jsonl')
        road=json.loads((folder/'road-readback.json').read_text())
        designation=json.loads((folder/'designation-record.json').read_text())
        if (len(observations)!=240 or len(signs)!=240 or
                road['driving_lane_ids']!=[-2,-1] or road['lane_direction_x']!=1 or
                designation['designated_direction_x']!=1 or
                designation['status']!='synthetic_unverified'):
            raise ValueError('Saved one-way readback differs')
        direction=1 if case=='designated' else -1
        visible={101:0,102:0}
        entry_visible=0;max_offset=0
        for i,(row,sign) in enumerate(zip(observations,signs)):
            if (row['frame']!=i or sign['frame']!=i or
                    abs(row['time_s']-(i+1)/20)>1e-6 or
                    sign['time_s']!=row['time_s'] or
                    row['native_frame']!=1000+i or sign['native_frame']!=row['native_frame'] or
                    row['case']!=case or row['source_kind']!='synthetic_cpu' or
                    sign['source_kind']!='synthetic_cpu' or row['lane_id']!=-1 or
                    row['ego_heading_deg']!=(0 if direction==1 else 180) or
                    row['ego_speed_mps']!=8 or row['ego_velocity_x_mps']!=direction*8 or
                    abs(row['ego_x_m']-((-20 if direction==1 else 220)+direction*8*(i+1)/20))>1e-4):
                raise ValueError('Independent saved one-way row join differs')
            for sign_id in set(sign['visible_sign_ids']):
                if sign_id not in visible:raise ValueError('Unknown saved sign id')
                visible[sign_id]+=1
            if i<40 and sign['visible_sign_ids']:entry_visible+=1
            max_offset=max(max_offset,abs(row['ego_y_m']+1.75))
        metric=item['measurement']
        if (metric['frames']!=240 or metric['occupied_frames']!=240 or
                metric['signed_ego_displacement_m']!=direction*95.6 or
                metric['movement_direction_x']!=direction or
                metric['direction_matches_designation']!=(direction==1) or
                metric['visible_sign_frame_counts']!={str(k):v for k,v in visible.items()} or
                metric['entry_visible_sign_frames']!=entry_visible or
                metric['maximum_lane_center_deviation_m']!=round(max_offset,3) or
                metric['designation_record_status']!='synthetic_unverified' or
                metric['designation_authority_verified'] or metric['physical_sign_verified'] or
                metric['legal_verdict'] is not None or metric['delivery_ready']):
            raise ValueError('Independent saved one-way metric differs')
        rows_checked+=240
    replayed=[];source=HERE/'saved-fixtures'/'designated'
    for mutation in ('wrong_expected_hash','missing_saved_frame','wrong_velocity',
                     'missing_sign_frame','wrong_designation_direction'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder=Path(temporary)/'saved';shutil.copytree(source,folder)
            if mutation=='missing_saved_frame':
                path=folder/'native-observed.jsonl';data=load(path);data.pop();write(path,data)
            elif mutation=='wrong_velocity':
                path=folder/'native-observed.jsonl';data=load(path)
                data[60]['ego_velocity_x_mps']=-8;write(path,data)
            elif mutation=='missing_sign_frame':
                path=folder/'sign-frames.jsonl';data=load(path);data.pop();write(path,data)
            elif mutation=='wrong_designation_direction':
                path=folder/'designation-record.json';data=json.loads(path.read_text())
                data['designated_direction_x']=-1;path.write_text(json.dumps(data)+'\n')
            try:
                measure(folder,{'native-observed.jsonl':'0'*64,
                                **{name:sha(folder/name) for name in FILES if name!='native-observed.jsonl'}}
                        if mutation=='wrong_expected_hash' else None)
            except (ValueError,TypeError):replayed.append(mutation)
            else:raise ValueError('Independent saved control accepted '+mutation)
    if seen!={'designated','opposite'} or rows_checked!=480:
        raise ValueError('Saved one-way coverage incomplete')
    receipt={'format':'c150916-independent-saved-audit-v1',
             'proof_sha256':sha(proof_path),'saved_rows_recomputed':rows_checked,
             'negative_controls_replayed':replayed,
             'original_native_observed':False,'delivery_ready':False}
    (HERE/'saved-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
