"""Independent CPU audit of the exact device source and pinned receipts."""
import hashlib
import json
from pathlib import Path

from device_direction_probe import check_saved_device_rows

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASE=HERE.name+'__device_direction'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    manifest=read(HERE/'draft-device-direction-manifest.json')
    entry=manifest['cases'][0]
    assert entry['case_id']==CASE and entry['construction_sha256']==sha(HERE/entry['construction'])
    construction=read(HERE/entry['construction'])
    assert construction['case_id']==CASE and construction['entrypoint']=='device_direction_entrypoint.py'
    assert len(construction['source_cameras'])==4
    assert {'device-survey-readback.json','traffic-control-device.jsonl'}<=set(construction['raw_sources'])
    recipe=read(ROOT/entry['fixture_recipe'])
    inventory={row['path']:row for row in recipe['sources']}
    for name in ('device-survey-readback.json','traffic-control-device.jsonl',
                 'video_frames.jsonl'):
        assert inventory[name]['sha256']==sha(ROOT/inventory[name]['source'])
    readback=read(ROOT/inventory['device-survey-readback.json']['source'])
    assert readback['source_kind']=='synthetic_native_sample'
    device=[json.loads(line) for line in
            (ROOT/inventory['traffic-control-device.jsonl']['source']).read_text().splitlines()]
    frames=[{'frame':json.loads(line)['carla_frame']} for line in
            (ROOT/inventory['video_frames.jsonl']['source']).read_text().splitlines()]
    measured=check_saved_device_rows(device,frames,readback,
                                     source_kind='synthetic_native_sample')
    assert measured['source_frames']==600 and measured['state_counts']['Red']==60
    assert measured['direction_applicability_verified'] is False
    assert measured['statutory_necessity_verified'] is False
    compatibility=read(HERE/'update113-device-compatibility-receipt.json')
    saved=read(HERE/'update113-device-saved-receipt.json')
    selection=read(HERE/'update113-device-offline-selection.json')
    assert compatibility['passed'] is True and saved['passed'] is True
    assert saved['recorded_only'] is True and saved['originals_preserved'] is True
    assert saved['timestamp_joins']=={'frames':600,'passed':True,
                                      'missing_original_trace_or_map':False}
    assert all(row['case_id']==CASE and row['construction_sha256']==entry['construction_sha256']
               for row in (compatibility,selection))
    assert saved['case_id']==CASE and saved['native_revision']['construction_sha256']==entry['construction_sha256']
    assert compatibility['measurement_examples']['device_direction_context']['value']['state_counts']==measured['state_counts']
    assert compatibility['negative_removed']=='traffic-control-device.jsonl'
    assert ('Missing required source: traffic-control-device.jsonl' in
            (HERE/'update113-device-negative-analysis.log').read_text())
    assert saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False
    return {'passed':True,'case_id':CASE,'source_frames':600,
            'state_counts':measured['state_counts'],
            'construction_sha256':entry['construction_sha256'],
            'compatibility_receipt_sha256':sha(HERE/'update113-device-compatibility-receipt.json'),
            'saved_receipt_sha256':sha(HERE/'update113-device-saved-receipt.json'),
            'original_native_verified':False,
            'direction_applicability_verified':False,
            'statutory_necessity_verified':False,
            'physical_or_legal_acceptance_claimed':False}


if __name__=='__main__':
    print(json.dumps(check(),indent=2,sort_keys=True))
