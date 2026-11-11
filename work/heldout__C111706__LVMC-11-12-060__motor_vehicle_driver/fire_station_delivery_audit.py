"""Independent source/decode and Native review audit for C111706 delivery."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'runtime'))
from scenario_pipeline.worker_exchange import media

from fire_station_measurement import SOURCES, measure


PREFIX='heldout__C111706__LVMC-11-12-060__motor_vehicle_driver__'
CAMERAS=('overview','approach','reference_corner','driver_reference')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(case,attempt,*,diagnostic_fixture=False):
    root=Path(attempt)
    config=json.loads((root/'config.json').read_text())
    report=json.loads((root/'analysis-report.json').read_text())
    result=json.loads((root/'result.json').read_text())
    if (not case.startswith(PREFIX) or config.get('selected_case_id')!=case or
            report.get('case_id')!=case or result.get('case_id')!=case):
        raise ValueError('Exact C111706 delivery identity differs')
    original=measure(root)
    recorded=report['measurements']['station_reversal']
    normalized=json.loads(json.dumps(original,allow_nan=False))
    if (normalized!=recorded.get('value') or
            normalized!=result['measured_values'].get('station_reversal')):
        raise ValueError('Original C111706 station measurement differs')
    for name in SOURCES:
        if recorded['sources'].get(name)!=digest(root/name):
            raise ValueError('Stale original C111706 source: '+name)
    if (original['subject_actor_id']==original['other_actor_id'] or
            original['last_frame']-original['first_frame']<2):
        raise ValueError('Original C111706 participants or frame span incomplete')
    mapping_sha=digest(root/'video_frames.jsonl')
    frames=original['last_frame']-original['first_frame']+1
    cameras={name:media.audit(root/(name+'.mkv'),frames,
                              mapping_sha256=mapping_sha,
                              receipt=root/('station-source-decode-'+name+'.json'))
             for name in CAMERAS}
    composed=media.audit(root/'raw.mkv',frames,mapping_sha256=mapping_sha,
                         receipt=root/'station-source-decode-primary.json')
    review_receipt=None
    if diagnostic_fixture:
        if not (root/'fixture-provenance.json').is_file() or (root/'capture-seal.json').exists():
            raise ValueError('C111706 diagnostic audit requires marked unsealed fixture')
    else:
        if (root/'fixture-provenance.json').exists():
            raise ValueError('Native C111706 audit rejects fixture provenance')
        acquisition_path=root/'acquisition-provenance.json'
        if not acquisition_path.is_file():
            raise ValueError('Native C111706 acquisition provenance missing')
        acquisition=json.loads(acquisition_path.read_text())
        if acquisition.get('provenance_kind')!='native' or acquisition.get('diagnostic_fixture') is not False:
            raise ValueError('Native C111706 acquisition provenance differs')
        station_source=config.get('station_source',{})
        if (station_source!=config.get('station_survey',{}).get('station_source') or
                station_source!=original['station_source']):
            raise ValueError('Native C111706 station source binding differs')
        if station_source.get('kind')=='authored_diagnostic':
            raise ValueError('Native C111706 audit rejects diagnostic station source')
        seal_path,exit_path=root/'capture-seal.json',root/'native-exit.json'
        if not seal_path.is_file() or not exit_path.is_file():
            raise ValueError('Native C111706 closure and owner exit missing')
        seal,owner=json.loads(seal_path.read_text()),json.loads(exit_path.read_text())
        if (seal.get('provenance_kind')!='native' or
                seal.get('restoration',{}).get('restored') is not True or
                owner.get('event')!='native_exit' or
                owner.get('capture_seal_sha256')!=digest(seal_path) or
                any(seal.get('sources',{}).get(name)!=digest(root/name) for name in SOURCES)):
            raise ValueError('Native C111706 source closure differs')
        review_path=root/'station-physical-pixel-review.json'
        if not review_path.is_file():
            raise ValueError('Native C111706 physical/pixel review missing')
        review=json.loads(review_path.read_text())
        if review.get('case_id')!=case or not review.get('reviewer'):
            raise ValueError('Native C111706 review identity incomplete')
        if any(review.get('original_sha256',{}).get(name)!=digest(root/name)
               for name in SOURCES):
            raise ValueError('Native C111706 review original binding differs')
        for label in ('subject_body','other_body','station_entrance','turn_area'):
            visible=review.get('visible',{}).get(label,{})
            camera=visible.get('camera')
            if (camera not in cameras or
                    visible.get('camera_sha256')!=cameras[camera]['video_sha256'] or
                    type(visible.get('video_frame')) is not int or
                    not 0<=visible['video_frame']<frames or
                    visible.get('observed') is not True):
                raise ValueError('Native C111706 pixel review missing: '+label)
        physical=review.get('physical',{})
        if (physical.get('station_asset_reviewed') is not True or
                physical.get('opposite_direction_turn_observed') is not True or
                physical.get('other_vehicle_observed') is not True or
                physical.get('no_contact_observed') is not True):
            raise ValueError('Native C111706 physical completion review missing')
        review_receipt={'path':review_path.name,'sha256':digest(review_path),
                        'reviewer':review['reviewer']}
    return {'format':'worker-delivery-audit','case_id':case,
            'scope':'synthetic C111706 software diagnostic' if diagnostic_fixture
                    else 'source-bound Native C111706 review',
            'original_sha256':{name:digest(root/name) for name in SOURCES},
            'participant_ids':[original['subject_actor_id'],original['other_actor_id']],
            'frames':frames,'cameras':cameras,
            'source_decode_receipt_path':str(root/'station-source-decode-primary.json'),
            'source_decode_receipt_sha256':digest(root/'station-source-decode-primary.json'),
            'source_decode_auditor_sha256':composed['auditor_sha256'],
            'physical_pixel_review':review_receipt,
            'checks':{'native_source':not diagnostic_fixture,'all_participants':True,
                      'time_join':True,'full_video_decode':True,
                      'actual_pixels':review_receipt is not None,
                      'physical_completion':review_receipt is not None},
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--diagnostic-fixture',action='store_true')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=audit(args.case,args.attempt,diagnostic_fixture=args.diagnostic_fixture)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_id':result['case_id'],'frames':result['frames'],
                      'checks':result['checks']}))


if __name__=='__main__':main()
