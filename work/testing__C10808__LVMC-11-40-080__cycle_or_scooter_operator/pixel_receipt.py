"""Run pinned complete decode with the C10808 four-view pixel checker."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',str(REPO/'.runtime-work/c10808-runtime-output'))
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange import media
from pixel_checks import check


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--video',required=True)
    parser.add_argument('--frame-map',required=True)
    parser.add_argument('--receipt',required=True)
    args=parser.parse_args()
    rows=[json.loads(line) for line in Path(args.frame_map).read_text().splitlines()
          if line.strip()]
    if not rows:raise ValueError('Original frame map is empty')
    result=media.audit(args.video,len(rows),
        checkers={'c10808_four_view_pixels':(sha(ROOT/'pixel_checks.py'),check)},
        mapping_sha256=sha(args.frame_map),receipt=args.receipt)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
