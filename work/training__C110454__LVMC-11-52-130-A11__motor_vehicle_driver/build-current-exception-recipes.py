"""Bind six 600-frame synthetic exception diagnostics to source bytes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=json.loads((HERE/'current-v2-witness_2-recipe.json').read_text())
SOURCES=HERE/'exception-polarity-sources'
PIXELS=ROOT/'.runtime-work/c110454-current-fallbacks/witness_2/primary-compat-v4/driver_reference.mkv'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,separators=(',',':'))+'\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    assert PIXELS.is_file(), 'Current witness source video required'
    for branch in (1,2,3):
        for polarity in (1,2):
            suffix=f'exception_{branch}_{polarity}'
            output=HERE/'current-v2-exception-source'/suffix
            old=SOURCES/suffix
            packet=json.loads((old/'exception_context.json').read_text())
            assert packet['synthetic_diagnostic'] is True
            packet['original_frames']=list(range(100,700))
            if branch==3 and polarity==2:
                packet['original_pixel_sha256']=sha(PIXELS)
            write(output/'exception_context.json',packet)
            extras=['exception_context.json']
            if polarity==2 and branch==1:
                extras += ['other_actor_history.jsonl','ego_response_history.jsonl']
            if polarity==2 and branch==2:
                extras += ['device_action_history.jsonl']
            for name in extras[1:]:
                prior=rows(old/name)
                assert len(prior)==480
                expanded=[]
                for i in range(600):
                    row=dict(prior[min(i,479)])
                    row['native_frame']=100+i
                    expanded.append(row)
                (output/name).write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in expanded))
            recipe=dict(BASE)
            recipe['sources']=[*BASE['sources'],*({'path':name,'source':str((output/name).relative_to(ROOT)),
                                                 'sha256':sha(output/name)} for name in extras)]
            if polarity==2 and branch in (2,3):
                construction=json.loads((HERE/'draft-current-statutory'/suffix/'primary/construction.json').read_text())
                road=next(item['content'] for item in construction['files'] if item['path']=='road.xodr')
                (output/'road.xodr').write_text(road)
                capture=json.loads((HERE/'current-v2-source/witness_2/capture/manifest.json').read_text())
                capture['sources']['road.xodr']=sha(output/'road.xodr')
                (output/'capture').mkdir(parents=True,exist_ok=True)
                (output/'capture/manifest.json').write_text(json.dumps(capture,separators=(',',':'))+'\n')
                recipe['sources']=[item for item in recipe['sources'] if item['path'] not in ('road.xodr','capture/manifest.json')]
                for name in ('capture/manifest.json',):
                    recipe['sources'].append({'path':name,'source':str((output/name).relative_to(ROOT)),
                                              'sha256':sha(output/name)})
            path=HERE/f'current-v2-{suffix}-recipe.json'
            path.write_text(json.dumps(recipe,indent=2)+'\n')
            assert max((output/name).stat().st_size for name in extras)<2*1024*1024
            print(suffix,sha(path),extras)

if __name__=='__main__':
    main()
