"""Run independent original A2 bus loading-stop audit on postprocessing records."""
import argparse
import json
from pathlib import Path

from delivery_audit import verify


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--review-directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    directory=args.review_directory.resolve()
    names=('source-chain.json','decode-audit.json','physical-audit.json','pixel-review.json',
           'activity-review.json','designation-review.json','core-joined.json')
    records=[]
    for name in names:
        path=(directory/name).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError('missing independent source review: '+name)
        records.append(json.loads(path.read_text()))
    receipt=verify(args.case,args.attempt,*records)
    if args.output.exists():
        raise ValueError('retain prior original audit')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('original A2 bus loading-stop audit passed: '+args.case)


if __name__=='__main__':
    main()
