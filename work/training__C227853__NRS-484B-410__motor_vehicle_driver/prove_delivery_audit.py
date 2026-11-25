"""Run positive and missing-original-source tests for both exact cases."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output=[]
    folder=HERE/'delivery-proofs'
    folder.mkdir(exist_ok=True)
    for suffix in ('controlled_'+str(i) for i in range(1,9)):
        case=HERE.name+'__'+suffix
        for negative in (False,True):
            name=suffix+('-negative' if negative else '-positive')+'.log'
            args=[sys.executable,str(HERE/'delivery_audit.py'),'--case',case,'--self-test']
            if negative:
                args.append('--negative')
            result=subprocess.run(args,capture_output=True,text=True,timeout=30)
            (folder/name).write_text(result.stdout+result.stderr)
            if (result.returncode==0)==negative:
                raise ValueError('Delivery audit test exit differs: '+name)
            if negative and 'Missing original source: exact original Native result' not in result.stderr:
                raise ValueError('Delivery audit negative missed exact source: '+name)
            output.append({'case_id':case,'negative':negative,
                           'exit_code':result.returncode,'log':str((folder/name).relative_to(HERE)),
                           'log_sha256':sha(folder/name)})
    print(json.dumps({'passed':True,'proofs':output},sort_keys=True))


if __name__=='__main__':
    main()
