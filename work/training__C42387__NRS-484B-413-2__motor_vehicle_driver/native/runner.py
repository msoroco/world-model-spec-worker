"""CPU-only business-turn request entrypoint."""
import json
from pathlib import Path
from signal_distance import check_config,read_and_measure


def offline_check(root):
 root=Path(root)
 result=check_config(json.loads((root/'config.json').read_text()),
                     (root/'business-turn-road.xodr').read_text())
 result['request_measure']=read_and_measure(root/'requested-track.jsonl',
                                           'authored_native_request')
 return result


def capture(*args,**kwargs):
 raise RuntimeError('Original Native right-turn and signal capture is not integrated')
