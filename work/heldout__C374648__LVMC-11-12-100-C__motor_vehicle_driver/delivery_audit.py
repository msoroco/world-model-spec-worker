"""Independent original-source and saved-output audit for exact center-lane cases."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange import physical_preparation
from turn_origin_comparison_audit import _source as turn_source
from center_use_comparison_audit import _source as straight_source

PREFIX=HERE.name+'__'

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()

def audit(case,source,processing,tamper=False):
    if not case.startswith(PREFIX):raise ValueError('Wrong exact center-turn case')
    source,processing=Path(source),Path(processing)
    receipt=json.loads(processing.read_text())
    if (receipt.get('case_id')!=case or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved exact-case status or identity differs')
    hashes=receipt['original_source_hashes'].copy()
    if tamper:hashes['case_context.json']='0'*64
    for name,expected in hashes.items():
        path=source/name
        if not path.is_file() or digest(path)!=expected:
            raise ValueError('Original source hash differs: '+name)
    short=case[len(PREFIX):]
    observed=(straight_source if short.startswith('straight') else turn_source)(source,case,decode_video=True)
    if set(('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'))-set(observed['hashes']):
        raise ValueError('Four original source cameras were not fully decoded')
    result_path=Path(receipt['result'])
    if not result_path.is_file() or digest(result_path)!=receipt['result_sha256']:
        raise ValueError('Saved analysis result source hash differs')
    result=json.loads(result_path.read_text())
    if (result.get('case_id')!=case or result.get('physical_acceptance_claimed') is not False or
            result.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved analysis result identity or verdict differs')
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    entry=next((e for e in manifest['cases'] if e['case_id']==case),None)
    if entry is None:raise ValueError('Case absent from exact manifest')
    if receipt['native_revision']['construction_sha256']!=entry['construction_sha256']:
        raise ValueError('Native construction revision differs')
    physical_preparation.validate(ROOT,HERE,entry)
    return {'case_id':case,'source_count':len(hashes),'joined_original_frames':len(observed['rows']),
            'four_source_cameras_full_decoded':True,'physical_protocol_checked':True,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True);parser.add_argument('--source',required=True);parser.add_argument('--processing',required=True);parser.add_argument('--tamper-source-hash',action='store_true');args=parser.parse_args()
    print(json.dumps(audit(args.case,args.source,args.processing,args.tamper_source_hash)))
