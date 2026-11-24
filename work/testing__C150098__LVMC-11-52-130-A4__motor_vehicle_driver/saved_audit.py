"""Independent source-hash and original 20 Hz history audit for C150098."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from hydrant import ASSIGNMENT, CASES, measure_original_history, validate_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt: Path, case_suffix: str, *, frames: int = 900):
    root = Path(attempt)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('saved attempt directory missing')
    manifest_path = root/'source-manifest.json'
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError('original source manifest missing')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    files = {}
    for name in ('site.json','original-hydrant-history.jsonl'):
        path = root/name;binding=manifest.get(name)
        if (not path.is_file() or path.is_symlink() or not isinstance(binding,dict)
            or binding.get('kind')!='original_native' or binding.get('sha256')!=sha(path)):
            raise ValueError('missing or stale original source: '+name)
        files[name]=path
    site=json.loads(files['site.json'].read_text(encoding='utf-8'))
    validate_site(site)
    case=next((c for c in CASES if c.suffix==case_suffix),None)
    if case is None:
        raise ValueError('unknown exact hydrant case')
    raw=files['original-hydrant-history.jsonl'].read_text(encoding='utf-8')
    lines=raw.splitlines()
    if len(lines)!=frames or any(not line.strip() for line in lines):
        raise ValueError('original frame count mismatch')
    rows=[json.loads(line) for line in lines]
    if any(row.get('site_sha256')!=manifest['site.json']['sha256'] for row in rows):
        raise ValueError('original site hash differs from history')
    result=measure_original_history(rows,site,case)
    return {'format':'worker-c150098-saved-hydrant-audit-v1',
            'assignment_id':ASSIGNMENT,'case_id':ASSIGNMENT+'__'+case_suffix,
            'frame_count':frames,'site_sha256':manifest['site.json']['sha256'],
            'original_history_sha256':manifest['original-hydrant-history.jsonl']['sha256'],
            'measurement':result,'physical_visibility_verified':False,
            'legal_verdict_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--case-suffix',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=audit(args.attempt,args.case_suffix)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':main()
