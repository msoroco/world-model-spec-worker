"""Source-bound synthetic comparison across five held-context lateral probes."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'update052-extreme-right-sweep-manifest.json'
INDEX=HERE/'update052-extreme-right-sweep-matrix-index.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def rows(path):return [json.loads(x) for x in path.read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)

def prove(manifest,index):
    require(index['manifest_sha256']==sha(MANIFEST),'Lateral matrix source differs')
    ordered=sorted(manifest['cases'],key=lambda e:e['authored_lateral_right_offset_m'])
    records=[]
    for entry in ordered:
        ident=entry['case_id']
        run=ROOT/'.runtime-work/c110919-update052-lateral-matrix'/sha(MANIFEST)[:12]/ident/'primary'
        source=run/'compatibility/native_samples.jsonl'
        report=read(run/'compatibility/analysis-report.json')
        data=rows(source)
        require(len(data)==480 and
                report['measurements']['extreme_right_lateral_sweep']['sources']['native_samples.jsonl']==sha(source),
                'Saved lateral source or measurement hash differs')
        records.append((entry,data,report,sha(source)))
    base=records[0][1]
    output=[]
    held=('signal_state_observed','other_traffic_signal_state_observed',
          'other_traffic_body_xy_m','other_traffic_center_xy_m',
          'other_traffic_speed_mps','walker_center_xy_m',
          'walker_conflict_occupied','traffic_launch_frame','speed_mps')
    for entry,data,report,digest in records:
        offset=entry['authored_lateral_right_offset_m']
        require(all(row.get('lateral_right_offset_m')==offset and
                    row.get('synthetic_diagnostic') is True for row in data),
                'Selected offset or synthetic provenance changed')
        for left,right in zip(base,data):
            require(all(left[key]==right[key] for key in held),
                    'Traffic, pedestrian, signal or speed context changed')
        measured=report['measurements']['extreme_right_lateral_sweep']['value']
        clearance=measured['minimum_right_edge_clearance_m']
        require(round(clearance,3)==round(.65-offset,3) and
                measured['legal_extreme_right_verdict'] is None,
                'Synthetic full-body clearance differs from controlled offset')
        output.append({'case_id':entry['case_id'],'authored_lateral_offset_m':offset,
            'measured_minimum_right_edge_clearance_m':clearance,
            'native_source_sha256':digest})
    return output

def main():
    manifest,index=read(MANIFEST),read(INDEX)
    comparisons=prove(manifest,index)
    negative={}
    wrong=copy.deepcopy(index);wrong['manifest_sha256']='0'*64
    try:prove(manifest,wrong)
    except ValueError as error:negative['wrong_matrix_source']=str(error)
    else:raise AssertionError('Changed source matrix accepted')
    wrong=copy.deepcopy(manifest);wrong['cases'][0]['authored_lateral_right_offset_m']=9
    try:prove(wrong,index)
    except ValueError as error:negative['changed_authored_control']=str(error)
    else:raise AssertionError('Changed authored control accepted')
    proof={'format':'c110919-lateral-controlled-synthetic-comparison-v1',
        'manifest_sha256':sha(MANIFEST),'index_sha256':sha(INDEX),
        'comparisons':comparisons,'held_context_fields':list(('signal_state_observed',
            'other_traffic_signal_state_observed','other_traffic_body_xy_m',
            'other_traffic_center_xy_m','other_traffic_speed_mps','walker_center_xy_m',
            'walker_conflict_occupied','traffic_launch_frame','speed_mps')),
        'negative_rejections':negative,'original_native_accepted':False,
        'legal_extreme_right_verdict':None}
    target=HERE/'update055-extreme-right-comparison-proof.json'
    target.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'points_checked':len(comparisons),'negative_rejections':len(negative),
        'proof_sha256':sha(target),'original_native_accepted':False}))

if __name__=='__main__':main()
