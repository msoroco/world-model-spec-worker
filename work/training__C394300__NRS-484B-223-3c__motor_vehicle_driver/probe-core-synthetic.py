"""Run the pinned Core converter on a generated 480-frame diagnostic capture."""
import importlib.util
import json
import pickle
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('saved_fixture_proof',HERE/'saved-fixture-proof.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from finalize import finalize  # noqa: E402
from worker_exchange.runtime_cli import process,render  # noqa: E402
from worker_exchange.media import audit  # noqa: E402
from traffic_spec_adapter.adapter import load_graph  # noqa: E402


def add_synthetic_graphs(attempt):
    source=ROOT/'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl'
    graph=load_graph(source)
    output=attempt/'capture/native/graphs/base';output.mkdir(parents=True)
    for frame in range(100,580):
        graph.graph['frame']=frame
        (output/f'{frame:08d}.pkl').write_bytes(pickle.dumps(graph,protocol=4))


def main():
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c394300-3c-core-probe-'))
    attempt=scratch/'attempt'
    print('scratch',scratch,flush=True)
    module.make_base(attempt,'below_50_ft')
    add_synthetic_graphs(attempt)
    finalize(attempt,attempt/'analysis-report.json')
    output=process(attempt,attempt/'converted',ROOT/'runtime/pipeline/library',
                   ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')
    config=json.loads((attempt/'config.json').read_text())
    video=render(attempt,attempt/'converted',config['case'])
    decoded=audit(video['video'],480,mapping_sha256=video['frame_map_sha256'],
                  receipt=attempt/'final-decode.json')
    print(json.dumps({'core':output,'render':video,
                      'final_decode':decoded,'scope':'synthetic local integration only; retained graph templates, no CARLA or acceptance'}))


if __name__=='__main__':main()
