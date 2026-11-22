"""CPU-only positive/negative proof for the independent paired sweep auditor."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

from traffic_sweep_audit import audit


ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    parser.add_argument('--negative',action='store_true');args=parser.parse_args()
    output=Path(args.output).resolve()
    if output.exists():shutil.rmtree(output)
    output.mkdir(parents=True)
    spec=importlib.util.spec_from_file_location('sweep_fixture',
                                                ROOT/'tests/test_traffic_sweep_audit.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    records=fixture.SweepAuditTests().inventory(output/'attempts')
    if args.negative:records=records[:-1]
    (output/'inventory.json').write_text(json.dumps({'records':records},indent=2)+'\n')
    result=audit(records)
    (output/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'variant_pairs':result['variant_pairs'],
                      'diagnostic_only':True}))


if __name__=='__main__':main()
