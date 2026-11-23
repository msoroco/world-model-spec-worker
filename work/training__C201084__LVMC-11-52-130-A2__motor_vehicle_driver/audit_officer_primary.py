"""Independent source/receipt audit of the synthetic officer primary."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name+'__officer_direction'
BASE = ROOT/'.runtime-work/c201084-officer-primary'
SOURCE = BASE/'compatibility-v3'
SAVED = BASE/'saved-v1/v0001'
CAMERAS = ('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    manifest = HERE/'draft-officer-direction-manifest.json'
    entry = read(manifest)['cases'][0]
    construction = HERE/entry['construction']
    compat_path = SOURCE/'compatibility.json'
    saved_path = SAVED/'processing.json'
    compat, saved = read(compat_path), read(saved_path)
    require(entry['case_id'] == CASE and
            sha(construction) == entry['construction_sha256'] and
            compat['case_id'] == saved['case_id'] == CASE and
            compat['construction_sha256'] ==
            saved['native_revision']['construction_sha256'] ==
            entry['construction_sha256'], 'Exact case/construction binding differs')
    require(compat['passed'] is True and
            'negative_case_source' in compat['checks'] and
            compat['negative_removed'] == 'police-officer-actor.jsonl' and
            saved['passed'] is True and saved['recorded_only'] is True and
            saved['missing_evidence'] is False,
            'Positive/negative compatibility or saved proof incomplete')
    frames = [json.loads(line) for line in
              (SOURCE/'video_frames.jsonl').read_text().splitlines()]
    rows = [json.loads(line) for line in
            (SOURCE/'police-officer-actor.jsonl').read_text().splitlines()]
    survey = read(SOURCE/'officer-survey-readback.json')
    require(len(frames) == len(rows) == 600 and
            len({row['carla_frame'] for row in frames}) == 600,
            'Incomplete or duplicated source frames')
    require(all(row['frame'] == frame['carla_frame'] and
                row['video_frame'] == index and
                row['officer_actor_id'] == survey['actor_id'] == 501 and
                row['officer_type_id'] == survey['type_id'] and
                row['source_kind'] == 'synthetic_native_sample' and
                row['police_authority_verified'] is False and
                row['direction_applicability_verified'] is False and
                row['statutory_necessity_verified'] is False
                for index, (row, frame) in enumerate(zip(rows, frames))),
            'Actor/frame join or authority claims differ')
    for name in ('officer-survey-readback.json','police-officer-actor.jsonl',
                 'video_frames.jsonl'):
        require(sha(SOURCE/name) == sha(SAVED/'analysis'/name) ==
                saved['original_source_hashes'][name],
                'Saved original source changed: '+name)
    require(all((SOURCE/(name+'.mkv')).is_file() and
                (SAVED/'analysis'/(name+'.mkv')).is_file()
                for name in CAMERAS), 'Four source cameras missing')
    analysis = read(SAVED/'analysis/analysis-report.json')
    result = read(SAVED/'analysis/result.json')
    value = analysis['measurements']['officer_direction_context']['value']
    require(value['source_frames'] == 600 and
            value['officer_actor_id'] == 501 and
            all(value[key] is False for key in
                ('police_authority_verified','direction_applicability_verified',
                 'statutory_necessity_verified')) and
            result['accepted'] is False and
            result['physical_acceptance_claimed'] is False and
            result['legal_verdict_claimed'] is False,
            'Analysis claims unsupported acceptance')
    receipt = {'format':'worker-independent-officer-diagnostic-audit',
               'case_id':CASE, 'candidate_id':'primary',
               'manifest_sha256':sha(manifest),
               'construction_sha256':sha(construction),
               'compatibility_sha256':sha(compat_path),
               'saved_sha256':sha(saved_path),
               'frames':600, 'source_cameras':list(CAMERAS),
               'original_actor_or_police_authority_verified':False,
               'physical_or_legal_completion_claimed':False,
               'passed':True}
    output = HERE/'current-officer-primary-audit.json'
    output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit(),sort_keys=True))
