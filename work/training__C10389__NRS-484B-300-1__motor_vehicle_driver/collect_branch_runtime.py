"""Retain compact active-runtime branch diagnostic receipts, never scratch bundles."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c10389-branch-compat-repo/.runtime-work'
DEST=HERE/'cases/branch-requests/current-proof'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source,target):
    if not source.is_file():raise ValueError('Missing active-runtime proof: '+str(source))
    data=source.read_bytes()
    if len(data)>2*1024*1024:raise ValueError('Returned proof file exceeds 2 MiB: '+str(source))
    if data.endswith(b'\n\n') or any(line.endswith((b' ',b'\t')) for line in data.splitlines()):
        raise ValueError('Returned proof has whitespace: '+str(source))
    target.write_bytes(data)
    return sha(target)


def main():
    DEST.mkdir(parents=True,exist_ok=True);entries=[]
    manifest_sha=sha(HERE/'branch-draft-manifest.json')
    for suffix in ('signal_red_stop','signal_green_proceed','officer_no_direction_stop','officer_directed_proceed'):
        for candidate in ('primary','fallback1'):
            stem=suffix+'-'+candidate;compat=SCRATCH/'compat-v2'/stem;saved=SCRATCH/'saved-v2'/stem/'v0001'
            target=DEST/stem;target.mkdir(exist_ok=True)
            checks={}
            for name,source in [('candidate-selection.json',compat/'candidate-selection.json'),
                    ('compatibility.json',compat/'compatibility.json'),
                    ('analysis.log',compat/'compatibility-analysis.log'),
                    ('negative-analysis.log',compat/'negative-analysis.log'),
                    ('processing.json',saved/'processing.json'),
                    ('saved-analysis.log',saved/'analysis.log')]:
                checks[name]=copy(source,target/name)
            receipt=json.loads((target/'compatibility.json').read_text())
            processing=json.loads((target/'processing.json').read_text())
            if receipt.get('passed') is not True or receipt.get('runtime_manifest_sha256')!=sha(ROOT/'runtime/SOURCE-MANIFEST.json'):
                raise ValueError('Active branch compatibility not passed')
            if processing.get('passed') is not True or processing.get('recorded_only') is not True:
                raise ValueError('Active branch saved processing not passed')
            entry={'case_id':HERE.name+'__'+suffix,'candidate_id':candidate,
                   'draft_manifest_sha256':manifest_sha,'file_sha256':checks,
                   'runtime_manifest_sha256':receipt['runtime_manifest_sha256'],
                   'diagnostic_only':True,'original_native_observed':False,'selected_delivery':False}
            path=target/'summary.json';path.write_text(json.dumps(entry,indent=2)+'\n')
            entries.append({'stem':stem,'summary_sha256':sha(path)})
    index={'format':'c10389-branch-active-runtime-diagnostic-index-v1',
           'draft_manifest_sha256':manifest_sha,'entries':entries,
           'candidate_count':len(entries),'selected_delivery':False}
    (DEST/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    return index


if __name__=='__main__':print(json.dumps({'candidate_count':main()['candidate_count']}))
