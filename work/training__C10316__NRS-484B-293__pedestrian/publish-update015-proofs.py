"""Retain small current CPU receipts and logs from ignored generated media."""
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(suffix,candidate):
    if suffix=='reference' and candidate=='primary':
        return ROOT/'.runtime-work/c10316-v15-reference-compat-primary-final'
    return ROOT/'.runtime-work'/('c10316-v15-'+suffix+'-compat-'+candidate)


def publish():
    manifest=HERE/'draft-execution-manifest.json'
    entries=[]
    for suffix in ('reference','contrast'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            origin=source(suffix,candidate)
            target=HERE/'update015-proofs'/suffix/candidate
            target.mkdir(parents=True,exist_ok=True)
            proof=json.loads((origin/'compatibility.json').read_text())
            if proof['passed'] is not True or proof['candidate_id']!=candidate:
                raise ValueError('Current compatibility proof missing or mismatched')
            files=[]
            for name,returned in (('compatibility.json','compatibility.json'),
                                  ('compatibility-analysis.log','analysis.log'),
                                  ('negative-analysis.log','negative-analysis.log')):
                src=origin/name;dest=target/returned
                shutil.copyfile(src,dest)
                if dest.stat().st_size>=2*1024*1024:
                    raise ValueError('Proof file exceeds worker return limit: '+returned)
                files.append({'path':dest.relative_to(HERE).as_posix(),'sha256':sha(dest)})
            entries.append({'case_id':proof['case_id'],'candidate_id':candidate,
                            'construction_sha256':proof['construction_sha256'],
                            'files':files})
    saved=[]
    for suffix in ('reference','contrast'):
      for candidate in ('primary','fallback1','fallback2','fallback3'):
        directory = ('c10316-v15-reference-saved-final' if suffix=='reference' and candidate=='primary'
                     else 'c10316-v15-contrast-saved' if suffix=='contrast' and candidate=='primary'
                     else f'c10316-v15-{suffix}-{candidate}-saved')
        origin=ROOT/'.runtime-work'/directory/'v0001'
        target=HERE/'update015-proofs'/suffix/candidate
        receipt=json.loads((origin/'processing.json').read_text())
        if (receipt['passed'] is not True or receipt['candidate_id']!=candidate
                or receipt['originals_preserved'] is not True or receipt['missing_evidence'] is not False):
            raise ValueError('Current saved-processing proof missing or mismatched')
        files=[]
        for name in ('processing.json','analysis.log'):
            src=origin/name;dest=target/('saved-'+name)
            shutil.copyfile(src,dest)
            files.append({'path':dest.relative_to(HERE).as_posix(),'sha256':sha(dest)})
        saved.append({'case_id':receipt['case_id'],'candidate_id':candidate,
                      'originals_preserved':receipt['originals_preserved'],
                      'missing_evidence':receipt['missing_evidence'],'files':files})
    index={'format':'c10316-update015-cpu-proof-index',
           'manifest_sha256':sha(manifest),
           'compatibility':entries,'saved_processing':saved,
           'scope':'unselected synthetic diagnostics; no Native or legal acceptance'}
    (HERE/'update015-proof-index.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({'compatibility':len(entries),'saved_processing':len(saved),
                      'manifest_sha256':index['manifest_sha256']}))


if __name__=='__main__':publish()
