"""Reproduce the pinned v2 fixture recipe's 3-frame capture boundary."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.fixture_recipe import inspect,materialize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def prove():
    base = 'runtime/pipeline/fixtures/retained-speed'
    source = 'work/'+HERE.name+'/alley-transition-summary.json'
    addition = {'path':'alley-transition-sources.json','source':source,
                'sha256':sha(REPO/source)}
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',prefix='alley-recipe-boundary-') as scratch:
        root = Path(scratch)
        recipe = {'format':'worker-fixture-recipe-v1','base':base,
                  'remove':['case.json','config.json','result.json'],
                  'additions':[addition]}
        valid = root/'recipe.json';write(valid,recipe)
        inspect(REPO,valid)
        fixture = root/'fixture';materialize(REPO,valid,fixture)
        counts = {name:len((fixture/name).read_text().splitlines()) for name in
                  ('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl')}
        assert counts == {name:3 for name in counts}
        assert not any((fixture/(name+'.mkv')).exists() for name in
                       ('overview','approach','facility','driver_reference'))
        shadow = root/'shadow.json'
        write(shadow,{**recipe,'additions':[{**addition,'path':'trace.jsonl'}]})
        try:inspect(REPO,shadow)
        except ValueError as error:
            assert 'shadows pinned source' in str(error)
            shadow_error = str(error)
        else:raise AssertionError('Pinned trace shadow unexpectedly allowed')
        return {'format':'c10052-alley-v2-recipe-boundary-v1',
            'retained_base':base,'retained_counts':counts,
            'four_alley_source_videos_present':False,
            'trace_replacement_error':shadow_error,
            'required_alley_join_frames':480,
            'scope':'frozen recipe capability reproducer; does not certify a case or block independent work'}


if __name__=='__main__':
    print(json.dumps(prove(),indent=2))
