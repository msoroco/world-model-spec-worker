"""Independent exact CPU proof audit for four device-direction candidates."""
import hashlib
import json
from pathlib import Path

from audit_device_direction import CASE, HERE, ROOT, read, sha
from device_direction_probe import check_saved_device_rows

IDS=('primary','fallback1','fallback2','fallback3')


def check(update='update114'):
    manifest=read(HERE/'draft-device-direction-fallback-manifest.json')
    entry=manifest['cases'][0]
    assert entry['case_id']==CASE
    candidates={'primary':{'id':'primary',
                           'construction':entry['construction'],
                           'construction_sha256':entry['construction_sha256']}}
    candidates.update({row['id']:row for row in entry['candidates']})
    assert set(candidates)==set(IDS)
    assert len({row['construction_sha256'] for row in candidates.values()})==4
    tunings=[]
    fixture_hashes=[]
    results={}
    for ident in IDS:
        candidate=candidates[ident]
        construction=read(HERE/candidate['construction'])
        assert sha(HERE/candidate['construction'])==candidate['construction_sha256']
        assert construction['case_id']==CASE
        assert len(construction['source_cameras'])==4
        config=json.loads(next(row['content'] for row in construction['files']
                               if row['path']=='config.json'))
        assert config['candidate_id']==ident and config['frames']==600
        assert config['direction_applicability_verified'] is False
        assert config['statutory_necessity_verified'] is False
        tunings.append(json.dumps(config.get('controller_tuning',{}),sort_keys=True))
        stem=update+'-device-'+ident
        selected=read(HERE/(stem+'-offline-selection.json'))
        positive=read(HERE/(stem+'-compatibility-receipt.json'))
        saved=read(HERE/(stem+'-saved-receipt.json'))
        assert selected['candidate_id']==positive['candidate_id']==saved['candidate_id']==ident
        assert selected['case_id']==positive['case_id']==saved['case_id']==CASE
        assert all(row['construction_sha256']==candidate['construction_sha256']
                   for row in (selected,positive))
        assert saved['native_revision']['construction_sha256']==candidate['construction_sha256']
        assert selected['manifest_sha256']==sha(HERE/'draft-device-direction-fallback-manifest.json')
        assert positive['passed'] is True and saved['passed'] is True
        assert saved['recorded_only'] is True and saved['originals_preserved'] is True
        assert saved['timestamp_joins']['passed'] is True and saved['timestamp_joins']['frames']==600
        assert positive['negative_removed']=='traffic-control-device.jsonl'
        assert ('Missing required source: traffic-control-device.jsonl' in
                (HERE/(stem+'-negative-analysis.log')).read_text())
        assert saved['physical_acceptance_claimed'] is False
        assert saved['legal_acceptance_claimed'] is False
        fixture_hashes.append(positive['fixture_sha256'])
        results[ident]={
            'construction_sha256':candidate['construction_sha256'],
            'compatibility_receipt_sha256':sha(HERE/(stem+'-compatibility-receipt.json')),
            'saved_receipt_sha256':sha(HERE/(stem+'-saved-receipt.json'))}
    assert len(set(tunings))==4
    assert len(set(fixture_hashes))==1
    recipe=read(ROOT/entry['fixture_recipe'])
    paths={row['path']:ROOT/row['source'] for row in recipe['sources']}
    readback=read(paths['device-survey-readback.json'])
    device=[json.loads(line) for line in paths['traffic-control-device.jsonl'].read_text().splitlines()]
    frames=[{'frame':json.loads(line)['carla_frame']}
            for line in paths['video_frames.jsonl'].read_text().splitlines()]
    measured=check_saved_device_rows(device,frames,readback,
                                     source_kind='synthetic_native_sample')
    assert measured['source_frames']==600 and measured['state_counts']['Red']==60
    return {'passed':True,'case_id':CASE,
            'manifest_sha256':sha(HERE/'draft-device-direction-fallback-manifest.json'),
            'candidate_count':4,'candidate_receipts':results,
            'shared_fixture_sha256':fixture_hashes[0],
            'source_frames':600,'original_native_verified':False,
            'direction_applicability_verified':False,
            'statutory_necessity_verified':False,
            'physical_or_legal_acceptance_claimed':False}


if __name__=='__main__':
    import sys
    print(json.dumps(check(sys.argv[1] if len(sys.argv)>1 else 'update114'),
                     indent=2,sort_keys=True))
