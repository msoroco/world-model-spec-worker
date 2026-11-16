"""Independent controlled-pair audit of measured right-pass engineering gaps."""
import copy
import json
from pathlib import Path

import check


ROOT=Path(__file__).resolve().parent


def require(ok,message):
    if not ok:raise ValueError(message)


def audit_pair(reference_config, reference_track, reference_measure,
               contrast_config, contrast_track, contrast_measure):
    check.validate_pair(reference_config,reference_track,
                        contrast_config,contrast_track)
    require(reference_measure['source_kind']==contrast_measure['source_kind'] and
            reference_measure['frames']==contrast_measure['frames']==240 and
            reference_config['case_id'].endswith('__reference') and
            contrast_config['case_id'].endswith('__contrast') and
            reference_measure['legal_safety_verdict'] is None and
            contrast_measure['legal_safety_verdict'] is None,
            'Measured pair source, duration or legal scope differs')
    require(reference_measure['observed_right_pass_frames']>0 and
            contrast_measure['observed_right_pass_frames']>0,
            'Measured pair lacks a right-side pass')
    for measured in (reference_measure,contrast_measure):
        observations=measured['observations']
        require(len(observations)==240 and
                all(row['source_kind']==measured['source_kind'] and
                    row['frame']==i for i,row in enumerate(observations)) and
                any(row['time_to_lead_center_s'] is not None for row in observations),
                'Measured pair lacks synchronized source-derived kinematics')
        require(measured['minimum_pass_body_surface_gap_m']>=0,
                'Measured pair surface gap differs')
    ref_gap=reference_measure['minimum_pass_body_surface_gap_m']
    con_gap=contrast_measure['minimum_pass_body_surface_gap_m']
    require(ref_gap>con_gap,
            'Measured lateral body gap does not preserve requested sweep ordering')
    return {'candidate_id':reference_config['candidate_id'],
            'reference_gap_m':ref_gap,'contrast_gap_m':con_gap,
            'source_kind':reference_measure['source_kind'],
            'diagnostic_only':reference_measure['source_kind']!='original_native',
            'legal_safety_verdict':None}


def load_candidate(witness,candidate,fixture,measure):
    folder=ROOT/'drafts'/witness/candidate
    config=json.loads((folder/'config.json').read_text())
    track=check.rows(folder/'requested-tracks.jsonl')
    rows,frames=fixture(track)
    return config,track,measure(rows,frames)


def rejected(args,label):
    try:audit_pair(*args)
    except (ValueError,KeyError,AssertionError):return label
    raise AssertionError('Comparison negative accepted: '+label)


def prove():
    from prove_capture_measure import fixture
    from measure_raw import measure
    positive=[];negative=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        args=[*load_candidate('reference',candidate,fixture,measure),
              *load_candidate('contrast',candidate,fixture,measure)]
        positive.append(audit_pair(*args))
        altered=copy.deepcopy(args);altered[3]['lead_requested_speed_mps']+=1
        negative.append(rejected(altered,'changed-lead-speed-'+candidate))
        altered=copy.deepcopy(args)
        altered[5]['minimum_pass_body_surface_gap_m']=altered[2]['minimum_pass_body_surface_gap_m']+.1
        negative.append(rejected(altered,'inverted-measured-gap-'+candidate))
        altered=copy.deepcopy(args);altered[5]['observed_right_pass_frames']=0
        negative.append(rejected(altered,'missing-contrast-pass-'+candidate))
    return {'format':'c146314-210-2-comparison-audit-v1',
            'positive_synthetic_pairs':positive,'negative_rejections':negative,
            'original_native_observed':False,'legal_safety_verdict':None}


if __name__=='__main__':
    print(json.dumps(prove(),sort_keys=True))
