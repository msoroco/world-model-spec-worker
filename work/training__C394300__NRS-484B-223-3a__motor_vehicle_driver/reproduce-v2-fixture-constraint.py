"""Reproduce the selected v2 recipe's source-row mismatch for this 480-frame case."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import inspect,materialize

BASE='runtime/pipeline/fixtures/retained-speed'
SOURCE=(FOLDER/'native/config.json').relative_to(ROOT).as_posix()
HASH=hashlib.sha256((ROOT/SOURCE).read_bytes()).hexdigest()


def recipe(target):
    return {'format':'worker-fixture-recipe-v1','base':BASE,
        'remove':['case.json','config.json','result.json'],
        'additions':[{'path':target,'source':SOURCE,'sha256':HASH}]}


def main():
    config=json.loads((FOLDER/'native/config.json').read_text())
    required=config['duration_s']*config['rate_hz']
    assert required==480
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work') as temporary:
        scratch=Path(temporary)
        positive=scratch/'allowed.json';positive.write_text(json.dumps(recipe('extra.json')))
        inspect(ROOT,positive)
        fixture=scratch/'fixture';materialize(ROOT,positive,fixture)
        rows={name:len((fixture/name).read_text().splitlines()) for name in
            ('trace.jsonl','video_frames.jsonl','capture/evidence.jsonl',
             'capture/native/frames.jsonl')}
        shadow=scratch/'shadow.json';shadow.write_text(json.dumps(recipe('trace.jsonl')))
        try:inspect(ROOT,shadow)
        except ValueError as error:rejection=str(error)
        else:raise AssertionError('Trace replacement unexpectedly accepted')
        assert set(rows.values())=={3} and rejection=='Fixture addition shadows pinned source'
        print(json.dumps({'case_frame_requirement':required,'pinned_base':BASE,
            'pinned_base_rows':rows,'replacement_rejection':rejection,
            'scope':'tested frozen recipe constraint; worker-owned construction remains unfinished'},
            sort_keys=True))


if __name__=='__main__':main()
