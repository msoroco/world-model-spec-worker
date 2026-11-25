"""Bind current exact candidate offline logs after running runtime.py offline."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
MANIFEST=ROOT/'draft-native-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[1]
        for item in [entry,*entry['candidates']]:
            candidate=item.get('id','primary')
            log=HERE/(suffix+'-'+candidate+'-offline.log')
            output=json.loads(log.read_text())
            if output.get('case_id')!=entry['case_id'] or output.get('candidate_id')!=candidate or output.get('offline_passed') is not True:
                raise ValueError('Exact candidate offline proof missing: '+suffix+'/'+candidate)
            source=ROOT/item['construction']
            if sha(source)!=item['construction_sha256']:
                raise ValueError('Candidate construction changed after offline check')
            item['offline']={'command':'.venv-cpu/bin/python runtime.py offline --manifest work/'+ROOT.name+'/draft-native-manifest.json --case '+entry['case_id']+' --candidate '+candidate,
                'construction_sha256':item['construction_sha256'],'exit_code':0,
                'log':str(log.relative_to(ROOT)),'log_sha256':sha(log)}
            item.pop('offline_pending',None)
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':
    bind()
