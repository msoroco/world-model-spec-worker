"""Positive and material negative source tests for paired departure audit."""
import json
import os
from pathlib import Path
import shutil
import tempfile

from audit_comparison import audit

HERE=Path(__file__).resolve().parent
FILES=('road.xodr','video_frames.jsonl','departure-context.json',
       'departure-trace.jsonl')


def reject(folder,pair,mutation,expected):
    clear=folder/pair[0]
    close=folder/pair[1]
    for suffix in pair:
        target=folder/suffix
        target.mkdir()
        for name in FILES:
            shutil.copyfile(HERE/'selected-source'/suffix/name,target/name)
    mutation(clear,close)
    try:
        audit(clear,close)
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise RuntimeError('Damaged comparison source accepted: '+expected)


def main():
    pairs=[('controlled_'+str(i),'controlled_'+str(i+1)) for i in (1,3,5,7,9,11)]
    positive={a+'__'+b:audit(HERE/'selected-source'/a,HERE/'selected-source'/b)
              for a,b in pairs}
    checks={
        'changed_map':(lambda a,b:(b/'road.xodr').write_text('changed\n'),'Fixed map'),
        'changed_context':(lambda a,b:(b/'departure-context.json').write_text(
            json.dumps({'different':True})+'\n'),'Fixed highway'),
        'changed_frame_map':(lambda a,b:(b/'video_frames.jsonl').write_text('[]\n'),
                             'Fixed map or original frame timing'),
        'changed_ego':(lambda a,b:(b/'departure-trace.jsonl').write_text(
            (b/'departure-trace.jsonl').read_text().replace('"ego_speed_mps":0',
                '"ego_speed_mps":1',1)),'Fixed ego'),
        'removed_position_contrast':(lambda a,b:(b/'departure-trace.jsonl').write_text(
            (b/'departure-trace.jsonl').read_text().replace('"traffic_xy_m":[-50.0',
                '"traffic_xy_m":[30.0',1)),'Requested initial traffic position')}
    temp_root=Path(os.environ.get('TMPDIR','/tmp'))
    for pair in pairs:
        for name,(mutation,expected) in checks.items():
            with tempfile.TemporaryDirectory(prefix='c227853-compare-',dir=temp_root) as temp:
                reject(Path(temp),pair,mutation,expected)
    print(json.dumps({'passed':True,'positive':positive,
                      'negative_mutations':list(checks)},sort_keys=True))


if __name__=='__main__':
    main()
