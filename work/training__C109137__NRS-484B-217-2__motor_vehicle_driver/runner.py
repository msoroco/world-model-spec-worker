"""Explicit-case CPU handoff for the source-hashed selected Native constructions."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]

def command(case,candidate,output,offline=False):
    config=json.loads((HERE/'config.json').read_text())
    if case not in config['supported_case_ids']:
        raise ValueError('Unknown exact case')
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    entry=next((entry for entry in manifest['cases'] if entry['case_id']==case),None)
    if entry is None or candidate not in ['primary']+[x['id'] for x in entry['candidates']]:
        raise ValueError('Unknown exact case candidate')
    output=Path(output).resolve()
    scratch=(REPO/'.runtime-work').resolve()
    if output!=scratch and scratch not in output.parents:
        raise ValueError('Output must be under .runtime-work')
    return [sys.executable,str(REPO/'runtime.py'),'offline' if offline else 'materialize',
            '--manifest',str(HERE/'execution-manifest.json'),'--case',case,
            '--candidate',candidate,'--output',str(output)]+(['--python',sys.executable] if offline else [])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--candidate',default='primary')
    parser.add_argument('--output',required=True)
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    raise SystemExit(subprocess.run(command(args.case,args.candidate,args.output,args.offline),cwd=REPO).returncode)

if __name__=='__main__':main()
