"""Audit the four candidate adjacent-box deposit/no-deposit contrast."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE=ROOT.name
DEPOSIT=BASE+'__mail_adjacent_deposit'
NO_DEPOSIT=BASE+'__mail_adjacent_no_deposit'
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
              if row['comparison_id']==BASE+'__mail_activity')
    if pair['case_ids']!=[DEPOSIT,NO_DEPOSIT] or \
            pair['deliberate_differences']!=['mail_deposit_event']:
        raise ValueError('Frozen mail activity comparison differs')
    saved={DEPOSIT:json.loads((ROOT/'update042-mail-adjacent-saved-matrix.json').read_text()),
           NO_DEPOSIT:json.loads((ROOT/'update042-mail-no-deposit-saved-matrix.json').read_text())}
    for candidate in CANDIDATES:
        active_files,active=package(DEPOSIT,candidate)
        absent_files,absent=package(NO_DEPOSIT,candidate)
        changed={key for key in set(active)|set(absent)
                 if active.get(key)!=absent.get(key)}
        if changed!={'case_id','selected_case_id','supported_case_ids','activity_request'}:
            raise ValueError('Mail activity pair changed fixed config: '+candidate)
        if active['activity_request']!='mail_deposit' or absent['activity_request'] is not None:
            raise ValueError('Mail activity request contrast differs')
        for name in ('red-curb-road.xodr','requested-tracks.jsonl',
                     'parking_controller.py','measure_exceptions.py','assignment-source.json'):
            if active_files[name]!=absent_files[name]:
                raise ValueError('Mail activity pair changed fixed source: '+name)
        attempts={DEPOSIT:REPO/'.runtime-work'/f'c150142-mail-adjacent-{candidate}-native-v3',
                  NO_DEPOSIT:REPO/'.runtime-work'/f'c150142-mail-no-deposit-{candidate}-native-v1'}
        versions={DEPOSIT:REPO/'.runtime-work'/f'c150142-mail-adjacent-{candidate}-result-v3/v0001',
                  NO_DEPOSIT:REPO/'.runtime-work'/f'c150142-mail-no-deposit-{candidate}-result-v1/v0001'}
        for case in (DEPOSIT,NO_DEPOSIT):
            receipts={row['candidate']:row for row in saved[case]['candidates']}
            if set(receipts)!=set(CANDIDATES) or receipts[candidate]['frames']!=361 or \
                    receipts[candidate]['full_final_decode'] is not True:
                raise ValueError('Mail activity terminal candidate missing')
            observed=json.loads((versions[case]/'analysis/result.json').read_text())[
                'measured_values']['signed_curb_observation']
            expected=['mail_deposit'] if case==DEPOSIT else []
            if observed['mailbox_present'] is not True or \
                    [row['name'] for row in observed['recorded_activity_events']]!=expected or \
                    observed['expeditious_mail_deposit_established'] is not None:
                raise ValueError('Mail activity saved observation differs')
        for name in ('native-raw-actors.jsonl','native-map-readback.json',
                     'video_frames.jsonl','trace.jsonl','overview.mkv','approach.mkv',
                     'reference_corner.mkv','driver_reference.mkv'):
            if digest(attempts[DEPOSIT]/name)!=digest(attempts[NO_DEPOSIT]/name):
                raise ValueError('Mail activity pair changed fixed synthetic source: '+name)
    return {'comparison_id':pair['comparison_id'],
            'candidates_compared':list(CANDIDATES),
            'mail_activity_proxy_isolated':True,
            'actual_mail_absence_established':False,
            'actual_mail_deposit_established':False,
            'expeditiousness_established':False,
            'original_native_observed':False}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
