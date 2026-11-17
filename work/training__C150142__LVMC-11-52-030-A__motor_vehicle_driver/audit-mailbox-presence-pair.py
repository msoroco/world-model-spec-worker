"""Check the four candidate mailbox-presence comparison on fixed CPU sources."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE=ROOT.name
ADJACENT=BASE+'__mail_adjacent_deposit'
NO_BOX=BASE+'__mail_no_box_deposit'
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(case,candidate):
    path=ROOT/('selected-primary' if candidate=='primary' else 'selected-fallbacks')/case.removeprefix(BASE+'__')
    if candidate!='primary':path/=candidate
    files={row['path']:row['content'] for row in json.loads((path/'construction.json').read_text())['files']}
    return files,json.loads(files['config.json'])


def check():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    pair=next(row for row in plan['comparisons']
              if row['comparison_id']==BASE+'__mailbox_adjacency')
    if pair['case_ids']!=[ADJACENT,NO_BOX] or \
            pair['deliberate_differences']!=['mailbox_presence']:
        raise ValueError('Frozen mail adjacency comparison differs')
    saved={ADJACENT:json.loads((ROOT/'update042-mail-adjacent-saved-matrix.json').read_text()),
           NO_BOX:json.loads((ROOT/'update042-mail-no-box-saved-matrix.json').read_text())}
    for candidate in CANDIDATES:
        adjacent_files,adjacent=package(ADJACENT,candidate)
        no_box_files,no_box=package(NO_BOX,candidate)
        changed={key for key in set(adjacent)|set(no_box)
                 if adjacent.get(key)!=no_box.get(key)}
        if changed!={'case_id','selected_case_id','supported_case_ids','road_sha256'}:
            raise ValueError('Mail pair changed fixed config: '+candidate)
        for name in ('requested-tracks.jsonl','parking_controller.py',
                     'mail_activity.py','measure_exceptions.py','assignment-source.json'):
            if adjacent_files[name]!=no_box_files[name]:
                raise ValueError('Mail pair changed fixed authored source: '+name)
        versions={ADJACENT:REPO/'.runtime-work'/f'c150142-mail-adjacent-{candidate}-result-v3/v0001',
                  NO_BOX:REPO/'.runtime-work'/f'c150142-mail-no-box-{candidate}-result-v3/v0001'}
        attempts={ADJACENT:REPO/'.runtime-work'/f'c150142-mail-adjacent-{candidate}-native-v3',
                  NO_BOX:REPO/'.runtime-work'/f'c150142-mail-no-box-{candidate}-native-v3'}
        for case in (ADJACENT,NO_BOX):
            receipts={row['candidate']:row for row in saved[case]['candidates']}
            if set(receipts)!=set(CANDIDATES) or \
                    receipts[candidate]['frames']!=361 or \
                    receipts[candidate]['full_final_decode'] is not True:
                raise ValueError('Mail pair terminal candidate missing')
            result=json.loads((versions[case]/'analysis/result.json').read_text())
            observed=result['measured_values']['signed_curb_observation']
            if result['case_id']!=case or \
                    observed['mailbox_present']!=(case==ADJACENT) or \
                    [event['name'] for event in observed['recorded_activity_events']]!=['mail_deposit'] or \
                    observed['expeditious_mail_deposit_established'] is not None:
                raise ValueError('Mail pair saved observation differs')
        for name in ('native-raw-actors.jsonl','native-mail-worker-actors.jsonl',
                     'native-mail-parcel-inventory.jsonl','video_frames.jsonl','trace.jsonl',
                     'overview.mkv','approach.mkv','reference_corner.mkv',
                     'driver_reference.mkv'):
            if digest(attempts[ADJACENT]/name)!=digest(attempts[NO_BOX]/name):
                raise ValueError('Mail pair changed fixed synthetic source: '+name)
        a=json.loads((attempts[ADJACENT]/'native-map-readback.json').read_text())
        b=json.loads((attempts[NO_BOX]/'native-map-readback.json').read_text())
        if {key for key in a if a[key]!=b[key]}!={'mailbox_readback'} or \
                not a['mailbox_readback']['present'] or b['mailbox_readback']['present']:
            raise ValueError('Mail pair map difference is not isolated')
    return {'comparison_id':pair['comparison_id'],
            'candidates_compared':list(CANDIDATES),
            'mailbox_presence_isolated':True,
            'actual_mail_deposit_established':False,
            'expeditiousness_established':False,
            'original_native_observed':False}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
