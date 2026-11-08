"""Copied paragraph (c)(1) source and 200-foot boundary controls."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent


def check(bundle):
    return subprocess.run([sys.executable,str(bundle/'check.py'),'--bundle',str(bundle)],
        capture_output=True,text=True)


def prove():
    manifest=json.loads((HERE/'offline/manifest.json').read_text())
    positives=negatives=0
    for row in manifest['entries']:
        bundle=HERE/row['bundle']
        result=check(bundle)
        capture=subprocess.run([sys.executable,str(bundle/'capture.py'),
            '--check','--bundle',str(bundle)],capture_output=True,text=True)
        if result.returncode or capture.returncode:
            raise ValueError('copied boundary positive failed: '+result.stderr+capture.stderr)
        checked=json.loads(result.stdout)
        if checked['c2_crossing_verified'] is not False:
            raise ValueError('paragraph (c)(2) incorrectly claimed')
        positives+=2
        for kind in ('assignment','plan','road','distance','route'):
            with tempfile.TemporaryDirectory() as temporary:
                target=Path(temporary)/'bundle';shutil.copytree(bundle,target)
                if kind=='assignment':
                    path=target/'assignment-source.json';obj=json.loads(path.read_text())
                    obj['law_record']['text']+=' changed';path.write_text(json.dumps(obj))
                elif kind=='plan':
                    path=target/'case-plan.json';obj=json.loads(path.read_text())
                    obj['source_law']['text']+=' changed';path.write_text(json.dumps(obj))
                elif kind=='road':
                    path=target/'unmarked-pass.xodr'
                    path.write_text(path.read_text().replace('type="shoulder"',
                        'type="driving"'))
                elif kind=='distance':
                    path=target/'config.json';obj=json.loads(path.read_text())
                    obj['requested_excursion_m']+=.1
                    path.write_text(json.dumps(obj))
                else:
                    path=target/'requested-tracks.jsonl';lines=path.read_text().splitlines()
                    obj=json.loads(lines[0]);obj['ego_y_m']+=1
                    lines[0]=json.dumps(obj);path.write_text('\n'.join(lines)+'\n')
                if check(target).returncode==0:
                    raise ValueError('changed '+kind+' accepted')
                negatives+=1
    receipt={'format':'c146314-paragraph-c1-copied-proof-v1',
        'positives':positives,'negatives':negatives,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'offline/proof-compatibility.json').write_text(
        json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(prove()))
