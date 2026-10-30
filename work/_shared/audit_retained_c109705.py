"""Audit a retained C109705 capture with current selected analysis, no Native replay."""
import argparse,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'work/_shared'))
import runtime002

def main():
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);p.add_argument('--owner-release-receipt',required=True);p.add_argument('--library',required=True);p.add_argument('--validator',required=True);a=p.parse_args()
 runtime=runtime002.prepare_runtime();runtime002.activate_runtime(ROOT,runtime)
 from worker_exchange.common import read
 from worker_exchange.saved_processing import run
 attempt=pathlib.Path(a.attempt).resolve();cfg=read(attempt/'config.json');cid=cfg.get('selected_case_id',cfg.get('case',{}).get('case_id'))
 manifest=ROOT/'work/_shared/legacy-captures/c109705-400-2a-v6/execution-manifest.json'
 if cid not in {e['case_id'] for e in read(manifest)['cases']}:raise ValueError('Retained capture is not the exact v6 selected_left_turn case')
 result=run(manifest,cid,attempt,pathlib.Path(a.output),a.library,a.validator,a.owner_release_receipt)
 print(__import__('json').dumps(result,indent=2))
if __name__=='__main__':main()
