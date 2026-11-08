"""Compare exact saved rotary passages under one fixed island readback."""
import argparse
import json
from pathlib import Path

from measure_saved import FILES,measure,sha


def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]


def compare(reference,contrast,expected_hashes=None):
    reference,contrast=Path(reference),Path(contrast)
    hashes={case:{name:sha(folder/name) for name in FILES}
            for case,folder in (('reference',reference),('contrast',contrast))}
    if expected_hashes is not None and hashes!=expected_hashes:
        raise ValueError('Rotary saved comparison source hashes differ')
    if hashes['reference']['island-readback.json']!=hashes['contrast']['island-readback.json']:
        raise ValueError('Rotary comparison fixed island readback differs')
    first,second=measure(reference),measure(contrast)
    if (first['case']!='reference' or second['case']!='contrast' or
            first['source_kind']!=second['source_kind']):
        raise ValueError('Rotary saved comparison case provenance differs')
    a,b=rows(reference/'native-observed.jsonl'),rows(contrast/'native-observed.jsonl')
    for i,(left,right) in enumerate(zip(a,b)):
        heading_sum=(left['ego_heading_deg']+right['ego_heading_deg'])%360
        left_body=sorted((round(x,4),round(-y,4)) for x,y in left['ego_body_xy_m'])
        right_body=sorted((round(x,4),round(y,4)) for x,y in right['ego_body_xy_m'])
        if (left['frame']!=i or right['frame']!=i or
                left['native_frame']!=right['native_frame'] or
                left['time_s']!=right['time_s'] or
                left['ego_speed_mps']!=right['ego_speed_mps'] or
                left['lane_id']!=right['lane_id'] or
                abs(left['ego_x_m']-right['ego_x_m'])>1e-5 or
                abs(left['ego_y_m']+right['ego_y_m'])>1e-5 or
                min(heading_sum,360-heading_sum)>1e-4 or
                left_body!=right_body):
            raise ValueError('Rotary saved fixed controls or mirrored body differs')
    if (first['angular_progress_rad']!=-second['angular_progress_rad'] or
            not first['half_circle_passage_observed'] or
            not second['half_circle_passage_observed'] or
            not first['continuous_requested_side'] or
            not second['continuous_requested_side']):
        raise ValueError('Rotary saved side contrast differs')
    return {'format':'c234827-saved-controlled-comparison-v1',
        'source_kind':first['source_kind'],'source_hashes':hashes,
        'paired_frames':240,'fixed_island_readback_bytes':True,
        'fixed_frame_time_speed_lane':True,
        'reference_measurement':first,'contrast_measurement':second,
        'side_frame_contrast':['left','right'],
        'original_native_observed':first['source_kind']=='original_native',
        'accepted_comparison':False,'legal_verdict':None,'delivery_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('reference',type=Path)
    parser.add_argument('contrast',type=Path)
    args=parser.parse_args()
    print(json.dumps(compare(args.reference,args.contrast),indent=2))
