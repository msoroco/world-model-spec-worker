"""Software-only positive/rejected audit probe for one exact C10808 case."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
from test_delivery_audit import DeliveryAuditTests
from delivery_audit import audit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--mode',choices=('positive','negative'),required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    path=Path(args.output).resolve()
    if path.exists():raise ValueError('Retain prior audit probe output')
    path.mkdir(parents=True)
    attempt,processing,decode,_=DeliveryAuditTests().fixture(path,args.case)
    if args.mode=='negative':
        (attempt/'sign-authorization-source').write_text('changed sign source')
    result=audit(attempt,processing,decode,args.case,
                 media_verify=lambda *a,**k: True)
    print(json.dumps({'software_fixture_only':True,'audit':result},indent=2))


if __name__=='__main__':main()
