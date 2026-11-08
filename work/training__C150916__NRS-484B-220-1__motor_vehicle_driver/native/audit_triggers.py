"""Independent row and negative replay audit of one-way fallback routing."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES
from triggers import route

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,data):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in data))


def audit():
    proof_path=HERE/'trigger-proof.json';proof=json.loads(proof_path.read_text())
    if (proof['format']!='c150916-measured-trigger-proof-v1' or
            proof['assignment_id']!=HERE.parent.name or
            proof['trigger_processor_sha256']!=sha(HERE/'triggers.py') or
            proof['saved_processor_sha256']!=sha(HERE/'measure_saved.py') or
            proof['original_native_observed'] or proof['delivery_ready'] or
            proof['selected_candidate'] is not None or len(proof['positives'])!=4 or
            [item['mutation'] for item in proof['negative_controls']]!=[
                'wrong_expected_hash','unknown_sign_id','bad_lane_offset'] or
            not all(item['rejected'] is True for item in proof['negative_controls'])):
        raise ValueError('One-way trigger proof provenance or status differs')
    folders={'designated':HERE/'saved-fixtures'/'designated',
             'opposite':HERE/'saved-fixtures'/'opposite',
             'entry_occluded':HERE/'trigger-fixtures'/'entry-occluded',
             'lane_deviation':HERE/'trigger-fixtures'/'lane-deviation'}
    seen=set();rows_checked=0
    for item in proof['positives']:
        name=item['variant']
        if name not in folders or name in seen:raise ValueError('One-way trigger fixture coverage differs')
        seen.add(name);folder=folders[name]
        hashes={file:sha(folder/file) for file in FILES}
        if hashes!=item['source_hashes']:raise ValueError('One-way trigger saved hashes differ')
        actors=load(folder/'native-observed.jsonl');signs=load(folder/'sign-frames.jsonl')
        designation=json.loads((folder/'designation-record.json').read_text())
        if len(actors)!=240 or len(signs)!=240:
            raise ValueError('One-way trigger saved row count differs')
        entry_visible=sum(bool(row['visible_sign_ids']) for row in signs[:40])
        max_offset=max(abs(row['ego_y_m']-(-1.75 if row['lane_id']==-1 else -5.25))
                       for row in actors)
        flags={'fallback1_slow_sign_approach':entry_visible==0,
               'fallback2_outer_lane_traverse':round(max_offset,3)>0.2,
               'fallback3_stop_before_entry':designation['status']!='reviewed_authority'}
        if item['triggered']!=flags:
            raise ValueError('Independent one-way routing metric differs')
        rows_checked+=240
    if seen!=set(folders) or rows_checked!=960:
        raise ValueError('One-way trigger coverage incomplete')
    replayed=[];source=folders['designated']
    for mutation in ('wrong_expected_hash','unknown_sign_id','bad_lane_offset'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder=Path(temporary)/'saved';shutil.copytree(source,folder)
            if mutation=='unknown_sign_id':
                path=folder/'sign-frames.jsonl';data=load(path)
                data[60]['visible_sign_ids']=[999];write(path,data)
            elif mutation=='bad_lane_offset':
                path=folder/'native-observed.jsonl';data=load(path)
                data[60]['ego_y_m']=-.75;write(path,data)
            try:route(folder,{'native-observed.jsonl':'0'*64}
                      if mutation=='wrong_expected_hash' else None)
            except (ValueError,TypeError):replayed.append(mutation)
            else:raise ValueError('One-way trigger negative replay accepted')
    receipt={'format':'c150916-independent-trigger-audit-v1',
             'proof_sha256':sha(proof_path),'saved_rows_recomputed':rows_checked,
             'negative_controls_replayed':replayed,
             'original_native_observed':False,'delivery_ready':False}
    (HERE/'trigger-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
