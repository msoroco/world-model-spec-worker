"""Independent software source-integrity audit of one saved C125763 attempt.

This is preparation evidence only. Original camera pixels and Native physical
completion need later independent local review before delivery acceptance.
"""
import hashlib
import json
import sys
from pathlib import Path

from capture_sources import CAMERAS
from runner import ASSIGNMENT, CASE_IDS


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def audit(attempt,analysis_name='saved-analysis.json',*,decode=False,expected_case=None):
    root=Path(attempt)
    required=('config.json','result.json','junction_context.json',
              'crossing_history.jsonl','controller_history.jsonl','video_frames.jsonl',
              'trace.jsonl','capture/evidence.jsonl',*(name+'.mkv' for name in CAMERAS),
              analysis_name)
    for name in required:
        require((root/name).is_file(),'Missing original/delivered source: '+name)
    cfg=json.loads((root/'config.json').read_text())
    result=json.loads((root/'result.json').read_text())
    report=json.loads((root/analysis_name).read_text())
    case=cfg.get('selected_case_id')
    require(cfg.get('assignment_id')==ASSIGNMENT and case in CASE_IDS and
            result.get('case_id')==case and report.get('case_id')==case,
            'Exact C125763 case identity differs')
    if expected_case is not None:
        require(case==expected_case,'Requested exact C125763 case differs')
    require(result.get('physical_acceptance_claimed') is False and
            report.get('physical_acceptance_claimed') is False and
            report.get('format')=='worker-c125763-yield-sign-saved-analysis',
            'Saved analysis makes an unsupported physical claim')
    hashes={name:sha(root/name) for name in required if name not in ('result.json',analysis_name)}
    asserted=result.get('source_evidence_hashes',{})
    require(all(asserted.get(name)==digest for name,digest in hashes.items()),
            'Native result source hash differs from original bytes')
    measurements=report.get('measurements')
    expected={'crossing_identity','entry_timing','relative_right_side',
              'device_qualification_context','opposite_left_turn_context',
              'yield_observation'}
    require(isinstance(measurements,dict) and set(measurements)==expected,
            'Six selected measurement outputs required')
    for key,row in measurements.items():
        sources=row.get('sources')
        require(isinstance(sources,dict) and bool(sources) and all(
            name in hashes and hashes[name]==digest for name,digest in sources.items()),
            'Measurement source hash differs: '+key)
    frames=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines()]
    history=[json.loads(line) for line in (root/'crossing_history.jsonl').read_text().splitlines()]
    require(len(frames)==len(history)==round(cfg['duration_s']*cfg['rate_hz']) and len(frames)>0,
            'Incomplete original frame count')
    require(all(frame.get('video_frame')==i and frame.get('carla_frame')==row.get('frame') and
                frame.get('time_s')==row.get('time_s') for i,(frame,row) in
                enumerate(zip(frames,history))), 'Original frame identity differs')
    context=json.loads((root/'junction_context.json').read_text())
    require(context.get('native_yield_sign_id') and all(
        row.get('governing_yield_sign_id')==context['native_yield_sign_id'] for row in history),
        'Governing sign ID changed in original frames')
    decoded={}
    if decode:
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'runtime'/'scenario_pipeline'))
        from worker_exchange import media
        mapping_sha256=hashes['video_frames.jsonl']
        media.check_four_view_sources({name:root/(name+'.mkv') for name in CAMERAS})
        for name,dimensions in CAMERAS.items():
            receipt=media.audit(root/(name+'.mkv'),len(frames),mapping_sha256=mapping_sha256)
            require(receipt['dimensions']==list(dimensions),
                    'Decoded original camera dimensions differ: '+name)
            decoded[name]={'frames':receipt['frames'],
                           'rgb_sequence_sha256':receipt['rgb_sequence_sha256'],
                           'source_sha256':receipt['video_sha256']}
    return {'format':'worker-c125763-software-delivery-audit',
            'case_id':case,'software_source_integrity_passed':True,
            'full_video_decode_passed':bool(decode),'decoded_cameras':decoded,
            'original_frame_count':len(frames),'source_hashes':hashes,
            'measurement_keys':sorted(measurements),
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
            'delivery_ready':False,
            'remaining':('Actual actor pixels and physical completion need independent local review'
                         if decode else 'Full video decode, actual actor pixels and physical completion need independent local review')}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--analysis',default='saved-analysis.json')
    parser.add_argument('--case');parser.add_argument('--decode',action='store_true')
    args=parser.parse_args();print(json.dumps(audit(args.attempt,args.analysis,
                            decode=args.decode,expected_case=args.case),indent=2))
