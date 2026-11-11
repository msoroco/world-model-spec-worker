"""Independent source-bound comparison of two original right-exit attempts.

The production entrypoint refuses synthetic rows and unreviewed delivery receipts.
Pure comparison helpers are also exercised on synthetic CPU rows in tests; those
tests do not create an accepted recording or a legal verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'training__C132497__LVMC-11-43-010-C2__motor_vehicle_driver'
CASES = {name: ASSIGNMENT+'__'+name for name in ('reference','contrast')}
FIXED = ('assignment_id','law_id','cell_id','actor','rate_hz','frames',
         'road_sha256','camera_policy','requested_speed_mps',
         'pre_entry_dwell_s','circulation_direction')
RECEIPT_CHECKS = {'native_source','all_participants','time_join',
                  'full_video_decode','actual_pixels','physical_completion'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    path = Path(path)
    require(path.is_file(),'Missing original comparison source: '+str(path))
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    require(path.is_file(),'Missing original comparison source: '+str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def compare(configs, observations):
    ref, contrast = (configs[name] for name in ('reference','contrast'))
    require(ref['case_id']==CASES['reference'] and
            contrast['case_id']==CASES['contrast'], 'Comparison case identity differs')
    require(ref['candidate_id']==contrast['candidate_id'],
            'Comparison candidate policies differ')
    for key in FIXED:
        require(ref.get(key)==contrast.get(key),
                'Comparison fixed condition changed: '+key)
    require(ref['requested_lane_id']==-2 and contrast['requested_lane_id']==-1,
            'Comparison does not request right versus adjacent circulating lane')
    require(ref['controller_intention_sha256']!=contrast['controller_intention_sha256'],
            'Comparison collapsed separately declared intentions')
    measured={}
    for name, expected_lane in (('reference',-2),('contrast',-1)):
        source=observations[name]
        require(len(source)==240,'Original comparison frame coverage differs: '+name)
        require(all(row.get('frame')==i and row.get('observed_road_id') in (20,21,22,23)
                    and row.get('observed_lane_id') in (-2,-1)
                    for i,row in enumerate(source)),
                'Original comparison actor/frame join differs: '+name)
        circle=[row for row in source if row['observed_road_id'] in (21,23)]
        exit_rows=[row for row in source if row['observed_road_id']==22]
        require(len(circle)>=10 and len(exit_rows)>=5 and
                source[0]['observed_road_id']==20 and source[-1]['observed_road_id']==22,
                'Original comparison right-exit phases incomplete: '+name)
        require(circle[-1]['observed_lane_id']==expected_lane and
                exit_rows[0]['observed_lane_id']==expected_lane,
                'Original comparison observed exit lane differs: '+name)
        measured[name]={'last_circulating_lane_id':circle[-1]['observed_lane_id'],
                        'first_exit_lane_id':exit_rows[0]['observed_lane_id'],
                        'circulating_frames':len(circle),'exit_frames':len(exit_rows)}
    return {'candidate_id':ref['candidate_id'],'fixed_conditions':list(FIXED),
            'deliberate_difference':'requested and observed circulating exit lane',
            'measured':measured}


def audit(reference, contrast, reference_receipt, contrast_receipt, output):
    attempts={'reference':Path(reference).resolve(),'contrast':Path(contrast).resolve()}
    require(attempts['reference']!=attempts['contrast'],
            'Comparison reuses one attempt for both cases')
    configs={}; observations={}; receipt_hashes={}
    for name,receipt_path in (('reference',reference_receipt),('contrast',contrast_receipt)):
        attempt=attempts[name]
        receipt=read(receipt_path)
        config_path=attempt/'config.json'
        raw_path=attempt/'native-raw-actors.jsonl'
        intention_path=attempt/'controller-intention.json'
        frame_path=attempt/'video_frames.jsonl'
        config=read(config_path); raw=rows(raw_path); intention=read(intention_path)
        require(receipt.get('format')=='worker-delivery-audit' and
                receipt.get('passed') is True and
                receipt.get('case_id')==CASES[name] and
                receipt.get('candidate_id')==config.get('candidate_id') and
                receipt.get('original_native_observed') is True and
                RECEIPT_CHECKS <= {key for key,value in
                    receipt.get('checks',{}).items() if value is True},
                'Original comparison delivery receipt incomplete: '+name)
        hashes=receipt.get('sources',{})
        for source,path in (('config.json',config_path),
                            ('native-raw-actors.jsonl',raw_path),
                            ('controller-intention.json',intention_path),
                            ('video_frames.jsonl',frame_path)):
            require(hashes.get(source)==sha(path),
                    'Original comparison source hash changed: '+name+'/'+source)
        require(all(row.get('source_kind')=='original_native' for row in raw) and
                intention.get('source_kind')=='authored_controller_route_before_motion' and
                intention.get('turn_direction')=='right' and
                intention.get('intended_exit_road_id')==22 and
                intention.get('case_id')==CASES[name] and
                intention.get('candidate_id')==config.get('candidate_id') and
                config.get('controller_intention_sha256')==sha(intention_path),
                'Original comparison provenance or intention differs: '+name)
        auditor=Path(__file__).with_name('delivery_audit.py')
        require(receipt.get('auditor_sha256')==sha(auditor) and
                receipt.get('source_result_sha256')==hashes.get('result.json') and
                receipt.get('frames')==240 and
                receipt.get('video_sha256')==hashes.get('raw.mkv') and
                receipt.get('frame_map_sha256')==hashes.get('video_frames.jsonl'),
                'Original comparison delivery auditor or sealed result differs: '+name)
        decode_path=Path(receipt.get('source_decode_receipt_path',''))
        require(decode_path.is_file() and
                receipt.get('source_decode_receipt_sha256')==sha(decode_path),
                'Original comparison decode receipt changed: '+name)
        import delivery_audit
        media=delivery_audit.media_module()
        require(receipt.get('source_decode_auditor_sha256')==sha(Path(media.__file__)),
                'Original comparison decode auditor changed: '+name)
        media.verify_receipt(attempt/receipt['video'],decode_path,240,
                             mapping_sha256=sha(frame_path),
                             required_checks={'c132497_reviewed_pixels':sha(auditor)})
        configs[name]=config; observations[name]=raw
        receipt_hashes[name]=sha(receipt_path)
    comparison=compare(configs,observations)
    result={'format':'c132497-independent-original-pair-v1','passed':True,
            'comparison_id':ASSIGNMENT+'__right_exit_lane_pair',
            'case_ids':[CASES['reference'],CASES['contrast']],
            'receipt_sha256':receipt_hashes,'attempts':{name:str(path)
                for name,path in attempts.items()},'comparison':comparison,
            'legal_verdict':None}
    output=Path(output)
    require(not output.exists(),'Retain prior original comparison audit')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference',required=True)
    parser.add_argument('--contrast',required=True)
    parser.add_argument('--reference-receipt',required=True)
    parser.add_argument('--contrast-receipt',required=True)
    parser.add_argument('--output',required=True)
    a=parser.parse_args()
    print(json.dumps(audit(a.reference,a.contrast,a.reference_receipt,
                           a.contrast_receipt,a.output),sort_keys=True))
