"""Diagnostic 900-frame Core/render attempt using retained graph templates."""
import importlib.util
import json
import os
import pickle
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
spec = importlib.util.spec_from_file_location('c102304_saved_fixture',HERE/'prove-saved-following.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from finalize import finalize
from worker_exchange.runtime_cli import process, render
from worker_exchange.media import audit
from traffic_spec_adapter.adapter import load_graph


def main():
    env = dict(os.environ)
    env['PATH'] = str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    os.environ['PATH'] = env['PATH']
    scratch = Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c102304-core-probe-'))
    attempt = scratch/'attempt'
    print('scratch',scratch,flush=True)
    module.make_base(attempt,'condition_a',env)
    source = ROOT/'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl'
    graph = load_graph(source)
    output = attempt/'capture/native/graphs/base'
    output.mkdir(parents=True)
    for frame in range(100,1000):
        graph.graph['frame'] = frame
        (output/f'{frame:08d}.pkl').write_bytes(pickle.dumps(graph,protocol=4))
    finalize(attempt,attempt/'analysis-report.json')
    converted = process(attempt,attempt/'converted',ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')
    config = json.loads((attempt/'config.json').read_text())
    rendered = render(attempt,attempt/'converted',config['case'])
    decoded = audit(rendered['video'],900,mapping_sha256=rendered['frame_map_sha256'],
                    receipt=attempt/'final-decode.json')
    print(json.dumps({'core':converted,'render':rendered,'final_decode_frames':decoded['frames'],
                      'scope':'synthetic local integration only; retained graph template, no CARLA or acceptance'},
                     default=str))


if __name__ == '__main__':
    main()
