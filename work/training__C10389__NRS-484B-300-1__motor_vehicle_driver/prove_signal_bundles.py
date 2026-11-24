"""CPU preflight for the two unselected Native signal constructions."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
BASE=HERE/'cases/branch-requests'
sys.path.insert(0,str(BASE))
from signal_check import check


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    positives=[]
    for suffix in ('signal_red_stop','signal_green_proceed'):
        bundle=BASE/suffix;row=check(bundle)
        construction=json.loads((bundle/'construction.json').read_text())
        if any((bundle/f['path']).read_text()!=f['content'] for f in construction['files']):
            raise ValueError('Inline signal construction differs')
        positives.append({'suffix':suffix,'construction_sha256':sha(bundle/'construction.json'),
                          'checked':row})
    negatives={}
    with tempfile.TemporaryDirectory(prefix='c10389-signal-',dir=HERE.parents[1]/'.runtime-work') as name:
        target=Path(name)
        source=BASE/'signal_red_stop'
        for f in source.iterdir():
            if f.is_file():shutil.copyfile(f,target/f.name)
        cfg=json.loads((target/'config.json').read_text())
        cfg['requested_signal_aspect']='green';(target/'config.json').write_text(json.dumps(cfg)+'\n')
        try:check(target)
        except ValueError as exc:negatives['aspect']=str(exc)
        else:raise AssertionError('Wrong signal aspect accepted')
        shutil.copyfile(source/'config.json',target/'config.json')
        tracks=(target/'requested-tracks.jsonl').read_text().splitlines();(target/'requested-tracks.jsonl').write_text('\n'.join(tracks[:-1])+'\n')
        try:check(target)
        except ValueError as exc:negatives['truncated_source']=str(exc)
        else:raise AssertionError('Truncated signal source accepted')
    return {'format':'c10389-signal-native-cpu-proof-v1','positive_bundles':positives,
            'negative_rejections':negatives,'native_executed':False,'selected_delivery':False}


if __name__=='__main__':
    proof=main();(BASE/'signal-bundles-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'positives':len(proof['positive_bundles']),
                      'negatives':len(proof['negative_rejections'])}))
