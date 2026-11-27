"""Retain an independent original safety-zone delivery audit after local saved processing."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from delivery_audit import audit
from worker_exchange.media import audit as audit_media

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--processed-root',type=Path,required=True)
    parser.add_argument('--case',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('retain prior original audit report')
    versions=sorted(args.processed_root.glob('v*/processing.json'))
    if not versions:raise ValueError('saved processing receipt missing')
    processing=versions[-1]
    mapping=args.attempt/'video_frames.jsonl'
    count=len(mapping.read_text(encoding='utf-8').splitlines())
    decode=processing.parent/'safety-zone-source-decode.json'
    audit_media(processing.parent/'analysis/raw.mkv',count,
        mapping_sha256=hashlib.sha256(mapping.read_bytes()).hexdigest(),receipt=decode)
    report=audit(args.attempt,processing,decode,args.case)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
