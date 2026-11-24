"""CPU-only taxi loading draft entrypoint."""
import json
from pathlib import Path
from taxi_loading import check_config, read_and_measure


def offline_check(root):
    root = Path(root)
    result = check_config(json.loads((root/'config.json').read_text()),
                          (root/'taxi-road.xodr').read_text())
    result['request_measure'] = read_and_measure(root/'requested-track.jsonl',
                                                 'authored_native_request')
    return result


def capture(*args, **kwargs):
    raise RuntimeError('Original Native taxi, curb and participant capture is not integrated')
