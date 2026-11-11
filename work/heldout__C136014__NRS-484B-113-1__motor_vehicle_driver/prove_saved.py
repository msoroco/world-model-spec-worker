"""Fixture-only saved-processing proof for the primary exact backing case."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE='heldout__C136014__NRS-484B-113-1__motor_vehicle_driver__reverse_clear_traffic_steady'

def files(root):
    return {str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

def command(*args):
    subprocess.run([sys.executable,'runtime.py',*map(str,args)],check=True,capture_output=True,text=True)

def run(manifest,validator,scratch,candidate='primary',case=CASE):
    repo=Path(__file__).resolve().parents[2]
    manifest=Path(manifest).resolve();validator=Path(validator).resolve();scratch=Path(scratch).resolve()
    if not validator.is_file():raise ValueError('Pinned decoder executable missing')
    entry=next((e for e in json.loads(manifest.read_text())['cases'] if e['case_id']==case),None)
    if entry is None:raise ValueError('Unknown exact backing case')
    recipe=repo/entry['fixture_recipe']
    with tempfile.TemporaryDirectory(dir=scratch,prefix='backing-saved-proof-') as raw:
        root=Path(raw)
        positive=root/'positive';fixture=root/'fixture';out=root/'processed'
        command('materialize','--manifest',manifest,'--case',case,'--candidate',candidate,'--output',positive)
        command('fixture','--recipe',recipe,'--output',fixture)
        shutil.copytree(fixture,positive,dirs_exist_ok=True)
        before=files(positive)
        command('process-saved','--manifest',manifest,'--case',case,'--attempt',positive,
                '--output',out,'--library',repo/'runtime/library','--validator',validator)
        after=files(positive)
        if before!=after:raise ValueError('Saved processing changed original acquisition')
        receipt=json.loads((out/'v0001/processing.json').read_text())
        if not receipt.get('passed') or receipt.get('missing_evidence') or receipt.get('timestamp_joins',{}).get('passed') is not True:
            raise ValueError('Positive saved processing did not complete')
        if receipt.get('physical_acceptance_claimed') or receipt.get('legal_acceptance_claimed'):
            raise ValueError('Fixture claimed acceptance')
        negative=root/'negative';shutil.copytree(positive,negative)
        (negative/'backing_history.jsonl').unlink()
        neg_out=root/'negative-processed'
        command('process-saved','--manifest',manifest,'--case',case,'--attempt',negative,
                '--output',neg_out,'--library',repo/'runtime/library','--validator',validator)
        neg_receipt=json.loads((neg_out/'v0001/processing.json').read_text())
        feedback=json.loads((neg_out/'v0001/feedback.json').read_text())
        if not neg_receipt.get('missing_evidence') or feedback.get('classification')!='incomplete_or_unavailable_law_evidence' or 'Missing required source: backing_history.jsonl' not in feedback.get('error',''):
            raise ValueError('Missing backing source was not rejected with actionable feedback')
        return {'format':'worker-saved-proof','case_id':case,'candidate_id':candidate,'positive_saved_processing':True,
                'positive_originals_preserved':True,'positive_frame_count':receipt['timestamp_joins']['frames'],
                'negative_missing_source_rejected':True,'negative_feedback_classification':feedback['classification'],
                'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--validator',required=True);p.add_argument('--scratch',default='.runtime-work');p.add_argument('--candidate',default='primary');p.add_argument('--case',default=CASE)
    a=p.parse_args();print(json.dumps(run(a.manifest,a.validator,a.scratch,a.candidate,a.case),indent=2))
if __name__=='__main__':main()
