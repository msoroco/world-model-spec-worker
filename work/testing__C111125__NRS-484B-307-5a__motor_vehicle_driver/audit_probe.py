"""Exercise the independent delivery auditor with synthetic source fixtures."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('audit_fixture',ROOT/'tests/test_delivery_audit.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    output=Path(args.output).resolve()
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True)
    attempt,processing,decode,case=fixture.DeliveryAuditTests().make(
        output,args.case.endswith('__yield_straight'))
    if case!=args.case:raise ValueError('audit probe selected another case')
    frame_count=len((attempt/'video_frames.jsonl').read_text().splitlines())
    video=output/'analysis/raw.mkv'
    video.unlink()
    decode.unlink()
    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                    '-f','lavfi','-i','color=c=green:s=64x64:r=20',
                    '-frames:v',str(frame_count),'-c:v','ffv1',str(video)],check=True)
    root=os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not root or not Path(root).resolve().is_relative_to((REPO/'.runtime-work').resolve()):
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import')
    sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
    from worker_exchange.media import audit as decode_audit
    decode_audit(video,frame_count,mapping_sha256=fixture.sha(attempt/'video_frames.jsonl'),receipt=decode)
    if args.negative:
        with (attempt/'signal-head-history.jsonl').open('a') as stream:stream.write('{}\n')
    result=fixture.delivery.audit(attempt,processing,decode,case)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
