"""Create labelled synthetic raw paragraph (a) signal controls."""
import argparse
import json
from pathlib import Path

from fixture_raw_geometry import build as build_geometry

def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write_rows(path,items):
    Path(path).write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in items))

def build(bundle,output):
    bundle,output=Path(bundle),Path(output)
    build_geometry(bundle,output)
    cfg=json.loads((bundle/'config.json').read_text())
    signal=rows(bundle/'saved/lead-light-observed.jsonl')
    actor=rows(output/'native-raw-actors.jsonl')
    review=rows(output/'frame-review.jsonl')
    for i,(a,r,l) in enumerate(zip(actor,review,signal)):
        assert a['frame']==r['frame']==l['frame']==i
        a['requested_lead_left_signal']=cfg['lead_left_signal_requested']
        a['observed_lead_left_blinker']=l['observed_lead_left_blinker']
        a['observed_lead_light_state']=32 if l['observed_lead_left_blinker'] else 0
        r['signal_pixel_reviewed']=False
        r['lead_left_signal_visible']=None
    write_rows(output/'native-raw-actors.jsonl',actor)
    write_rows(output/'frame-review.jsonl',review)
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();print(build(a.bundle,a.output_dir))
