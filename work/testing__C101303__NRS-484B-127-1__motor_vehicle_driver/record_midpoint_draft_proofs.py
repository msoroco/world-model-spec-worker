"""Bind exact midpoint offline, compatibility and saved-processing CPU proofs."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'midpoint-draft-manifest.json'
OUT=ROOT/'midpoint-draft'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    case=manifest['cases'][0]
    rows=[]
    for candidate,selection in [('primary',case),*[(x['id'],x) for x in case['candidates']]]:
        construction=ROOT/selection['construction']
        if sha(construction)!=selection['construction_sha256']:
            raise ValueError('Midpoint construction changed')
        offline=OUT/f'{candidate}-offline.log'
        compat_log=OUT/f'{candidate}-compatibility.log'
        saved_log=OUT/f'{candidate}-saved.log'
        for path in (offline,compat_log,saved_log):
            if not path.is_file() or not path.read_text().strip():
                raise ValueError('Missing exact CPU proof log: '+str(path))
        attempt=REPO/'.runtime-work/c101303-midpoint-draft-compat'/candidate
        saved=REPO/'.runtime-work/c101303-midpoint-draft-saved'/candidate/'v0001/processing.json'
        compat=json.loads((attempt/'compatibility.json').read_text())
        processing=json.loads(saved.read_text())
        if (compat.get('passed') is not True or compat.get('case_id')!=case['case_id']
                or compat.get('candidate_id')!=candidate
                or compat.get('construction_sha256')!=selection['construction_sha256']
                or sha(attempt/'compatibility-analysis.log')!=compat['log_sha256']
                or sha(attempt/'negative-analysis.log')!=compat['negative_log_sha256']):
            raise ValueError('Midpoint compatibility/negative proof changed: '+candidate)
        if (processing.get('passed') is not True or processing.get('recorded_only') is not True
                or processing.get('originals_preserved') is not True
                or processing.get('candidate_id')!=candidate
                or processing['analysis_revision']['construction_sha256']!=selection['construction_sha256']
                or processing['analysis_revision']['runtime_manifest_sha256']!=manifest['runtime_manifest_sha256']):
            raise ValueError('Midpoint saved proof changed: '+candidate)
        target=OUT/'proofs'/candidate
        target.mkdir(parents=True,exist_ok=True)
        for source,name in ((attempt/'compatibility.json','compatibility.json'),
                            (attempt/'compatibility-analysis.log','analysis.log'),
                            (attempt/'negative-analysis.log','negative.log'),
                            (saved,'saved-processing.json')):
            shutil.copyfile(source,target/name)
        rows.append({'candidate_id':candidate,
                     'construction_sha256':selection['construction_sha256'],
                     'offline_log_sha256':sha(offline),
                     'compatibility_log_sha256':sha(compat_log),
                     'saved_log_sha256':sha(saved_log),
                     'compatibility_receipt_sha256':sha(target/'compatibility.json'),
                     'negative_log_sha256':sha(target/'negative.log'),
                     'saved_receipt_sha256':sha(target/'saved-processing.json')})
    (OUT/'proof-index.json').write_text(json.dumps({
        'format':'c101303-midpoint-draft-cpu-proofs',
        'case_id':case['case_id'],'manifest_sha256':sha(MANIFEST),
        'diagnostic_only':True,'physical_acceptance_claimed':False,
        'legal_acceptance_claimed':False,'proofs':rows},indent=2)+'\n')
    print('exact midpoint primary and three fallbacks passed offline, compatibility and recorded-only saved processing')


if __name__=='__main__':
    main()
