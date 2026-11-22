"""Exercise the delivery auditor with a bounded synthetic original-shaped fixture."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('audit_fixture',ROOT/'tests/test_delivery_audit.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    output=Path(args.output).resolve()
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True)
    attempt,processing,decode,case=fixture.DeliveryAuditTests().fixture(output,args.case)
    if case!=args.case:raise ValueError('audit probe selected another case')
    if args.negative:
        with (attempt/'encounter-history.jsonl').open('a') as stream:stream.write('{}\n')
    result=fixture.audit(attempt,processing,decode,case,media_verify=lambda *a,**k:True)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
