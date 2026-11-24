"""CPU checks for the root Native request and source channel guard."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from runner import inspect
from source_observations import rows


def main():
    assert inspect()['source_request_checked'] is True
    config=json.loads((HERE/'config.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    channels={c['name'] for c in config['recording_description']['channels']}
    assert len(config['cameras'])==4 and config['duration_s']==30
    assert {item['name'] for item in plan['observations']}<=channels
    assert set(plan['source_observation_mapping'])=={item['name'] for item in plan['observations']}
    fixture=HERE/'native/device/offline/raw-fixtures/probe_1/primary'
    try:
        list(rows(fixture))
    except ValueError as exc:
        assert str(exc)=='Complete restored original Native attempt required'
    else:
        raise AssertionError('Synthetic readback was accepted as original')
    print(json.dumps({'root_request_checked':True,'camera_count':4,'source_channels':11,
                      'synthetic_source_rejected':True,'original_native_observed':False}))


if __name__=='__main__':
    main()
