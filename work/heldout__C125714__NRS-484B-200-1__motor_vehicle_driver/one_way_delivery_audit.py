"""Independent original-source and four-camera audit of one-way diagnostics."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from one_way_measurement import measure_one_way


CASE='heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__posted_one_way'
CAMERAS=('overview','approach','reference_corner','driver_reference')


def audit(attempt,analysis,*,decoder=None):
    root=Path(attempt)
    config=json.loads((root/'config.json').read_text())
    report=json.loads(Path(analysis).read_text()) if not isinstance(analysis,dict) else analysis
    if config.get('selected_case_id')!=CASE or report.get('case_id')!=CASE:
        raise ValueError('Wrong exact one-way audit case')
    measured=measure_one_way(root)
    item=report.get('measurements',{}).get('posted_one_way_context',{})
    if item.get('value')!=measured or item.get('sources')!=measured['sources']:
        raise ValueError('One-way analysis differs from original source recomputation')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    count=len(measured['observations'])
    sources={}
    for camera in CAMERAS:
        path=root/(camera+'.mkv')
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing original one-way camera: '+camera)
        decoded=decoder(path,count,mapping_sha256=measured['sources']['video_frames.jsonl'])
        if decoded.get('frames')!=count:
            raise ValueError('One-way camera frame count differs: '+camera)
        sources[camera+'.mkv']={'source_sha256':sha256(path.read_bytes()).hexdigest(),
                                'decode':decoded}
    return {'format':'worker-one-way-delivery-audit','case_id':CASE,
            'source_sha256':measured['sources'],'frame_count':count,
            'camera_decodes':sources,'measurement_recomputed':True,
            'designation_verified':False,'posting_authority_verified':False,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--analysis',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior one-way audit receipt')
    output.write_text(json.dumps(audit(args.attempt,args.analysis),indent=2)+'\n')


if __name__=='__main__':
    main()
