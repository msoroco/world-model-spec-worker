"""Case-specific saved measurements for pinned compatibility; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import measure

SOURCES=('scene.xodr','road_geometry.json','declared_purpose.json','native_samples.jsonl')


def _required(folder,name):
    path=Path(folder)/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def purpose_movement(folder):
    result=measure(folder)
    return {'source_kind':result['source_kind'],
            'declared_purpose':result['declared_purpose'],
            'declared_purpose_is_observed_driver_intent':False,
            'movement':result['measured'],
            'requested_movement_observed_in_saved_rows':result['requested_movement_observed_in_saved_rows'],
            'legal_verdict':None}


def analysis_report(folder):
    folder=Path(folder)
    config=json.loads(_required(folder,'config.json').read_text())
    for name in SOURCES:_required(folder,name)
    return {'format':'c394300-3a-saved-analysis-v1','case_id':config['case_id'],
            'draft_only':True,'selected':False,
            'measurements':{'center_turn_purpose_and_movement':{
                'method':'purpose_movement','value':purpose_movement(folder),
                'sources':{name:_sha(folder/name) for name in SOURCES}}},
            'physical_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();output=Path(args.output)
    if output.exists():raise ValueError('Retain original analysis report; use fresh output')
    output.write_text(json.dumps(analysis_report(args.attempt),indent=2)+'\n')


if __name__=='__main__':main()
