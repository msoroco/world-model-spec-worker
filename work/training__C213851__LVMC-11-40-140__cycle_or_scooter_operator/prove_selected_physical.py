"""Source-bound synthetic crossing and owner-lifecycle proof mechanics."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=('probe_01','probe_02'),required=True)
    parser.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'),required=True)
    parser.add_argument('--output')
    args=parser.parse_args()
    if args.kind=='lifecycle':
        print(json.dumps({'events':['capture_finished','encoders_closed','restoration_verified',
            'native_exit','owner_released','saved_processing_started'],
            'premature_processing_rejected':True}))
        return
    if not args.output:
        parser.error('--output required')
    source_path=HERE/'cases'/args.case/'diagnostic.json'
    files=json.loads(source_path.read_text())['files']
    rows=[json.loads(line) for line in files['sidewalk-native.jsonl'].splitlines()]
    if len(rows)!=600 or any(row['source_kind']!='synthetic_native_sample' for row in rows):
        raise ValueError('Synthetic Native sidewalk source contract changed')
    source={'path':str(source_path.relative_to(HERE)),'sha256':sha(source_path),
        'embedded_source':'files.sidewalk-native.jsonl'}
    if args.kind=='missing_evidence':
        status,count='unverified',0
    elif args.kind=='incomplete_motion':
        status,count='not_met',20
    else:
        status,count='met',600
    selected=rows[:count]
    if any(row['rider_id']!=1 or row['pedestrian_id']!=2 or row['frame']!=i
           for i,row in enumerate(selected)):
        raise ValueError('Rider/pedestrian Native source identity changed')
    method='joined original-shaped 600-frame rider/pedestrian histories and surveyed sidewalk boundary'
    check={'status':status,'method':method,'sources':[source],
        'source_rows_used':count,'physical_acceptance_claimed':False,
        'legal_threshold_claimed':False}
    result={'format':'c213851-synthetic-crossing-physical-outcome-v1',
        'case_id':HERE.name+'__'+args.case,'provenance_kind':'synthetic_fixture',
        'diagnostic_fixture':True,'native_executed':False,
        'physical_acceptance_claimed':False,'legal_verdict_claimed':False,
        'physical_checks':{'maneuver':check},'maneuver_completed':status=='met',
        'realized_observables':{'crossing_source_rows':{'value':count,'unit':'frames',
            'method':method,'sources':[source]}} if status=='met' else {}}
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_id':result['case_id'],'status':status,'result_sha256':sha(path)}))


if __name__=='__main__':
    main()
