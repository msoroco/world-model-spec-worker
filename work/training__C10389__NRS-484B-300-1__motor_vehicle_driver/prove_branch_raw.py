"""CPU verification of eight synthetic branch fixture sources and provenance guard."""
import hashlib
import json
from pathlib import Path
from branch_measurement import measure

HERE=Path(__file__).resolve().parent
BASE=HERE/'cases/branch-requests'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    checks=[]
    for suffix in ('signal_red_stop','signal_green_proceed','officer_no_direction_stop','officer_directed_proceed'):
        for candidate in ('primary','fallback1'):
            bundle=BASE/(suffix if candidate=='primary' else suffix+'-'+candidate)
            raw=bundle/'raw-fixture';cfg=json.loads((bundle/'config.json').read_text())
            source=[json.loads(line) for line in (raw/'native-raw-actors.jsonl').read_text().splitlines()]
            videos=[json.loads(line) for line in (raw/'video_frames.jsonl').read_text().splitlines()]
            requests=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
            if not (len(source)==len(videos)==len(requests)):raise ValueError('Raw source count differs')
            if len(source)!=600:raise ValueError('Short raw branch fixture')
            for index,(actor,video,request) in enumerate(zip(source,videos,requests)):
                if (actor['frame']!=index or actor['native_frame']!=video['native_frame'] or
                        actor['requested_ego_x_m']!=request['requested_ego_x_m'] or
                        actor['source_kind']!='synthetic_cpu'):
                    raise ValueError('Synthetic branch source join differs')
            kind='signal' if suffix.startswith('signal_') else 'officer'
            condition=cfg['requested_signal_aspect'] if kind=='signal' else cfg['requested_officer_direction']
            try:measure(raw,kind,condition)
            except ValueError as exc:
                if str(exc)!='Complete restored original Native attempt required':raise
            else:raise AssertionError('Synthetic branch fixture accepted as original')
            checks.append({'case_id':cfg['case_id'],'candidate_id':candidate,
                           'actor_sha256':sha(raw/'native-raw-actors.jsonl'),
                           'original_source_rejected':True})
    return {'format':'c10389-branch-raw-cpu-proof-v1','checks':checks,
            'synthetic_fixture_count':len(checks),'native_executed':False,
            'original_native_observed':False,'selected_delivery':False}


if __name__=='__main__':
    result=main();path=BASE/'raw-fixture-proof.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'synthetic_fixtures':result['synthetic_fixture_count']}))
