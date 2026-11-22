"""Exercise the exact pair through source audits and fixed-condition comparison."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

from comparison_audit import audit as compare
from response_history_audit import audit as audit_response_history

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True);parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    output=Path(args.output).resolve()
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True)
    spec=importlib.util.spec_from_file_location('audit_fixture',ROOT/'tests/test_delivery_audit.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    records=[];attempts=[]
    for label in ('clear_path','crossing'):
        folder=output/label;folder.mkdir()
        case=ROOT.name+'__wheelchair_'+label
        attempt,processing,decode,returned=fixture.DeliveryAuditTests().fixture(folder,case)
        if returned!=case:raise ValueError('comparison fixture selected another case')
        records.append(fixture.audit(attempt,processing,decode,case,media_verify=lambda *a,**k:True))
        attempts.append(attempt)
    if args.negative:records[1]['ego_route_sha256']='changed-route-fingerprint'
    result=compare(*records)
    result['response_history_audit']=audit_response_history(*attempts,*records)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
