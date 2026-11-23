"""Independent audit of four final-manifest synthetic officer probes."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name+'__officer_direction'
CAMERAS = ('overview','approach','reference_corner','driver_reference')
CANDIDATES = ('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    manifest_path = HERE/'draft-officer-direction-fallback-manifest.json'
    manifest = read(manifest_path)
    require(len(manifest['cases']) == 1 and
            manifest['cases'][0]['case_id'] == CASE,
            'Final officer case selection differs')
    entry = manifest['cases'][0]
    selections = {'primary': (entry['construction'],
                               entry['construction_sha256'])}
    selections.update({row['id']:(row['construction'],row['construction_sha256'])
                       for row in entry['candidates']})
    require(set(selections) == set(CANDIDATES), 'Four candidate set differs')
    seen_constructions = set()
    seen_tunings = set()
    receipt = {'format':'worker-independent-officer-candidate-audit',
               'case_id':CASE, 'manifest_sha256':sha(manifest_path),
               'candidates':{}, 'synthetic_native_sample':True,
               'original_actor_or_police_authority_verified':False,
               'physical_or_legal_completion_claimed':False}
    common_sources = None
    for candidate in CANDIDATES:
        name, expected = selections[candidate]
        construction_path = HERE/name
        construction = read(construction_path)
        require(sha(construction_path) == expected and
                construction['case_id'] == CASE,
                'Construction hash/identity differs: '+candidate)
        config = json.loads(next(row['content'] for row in
                           construction['files'] if row['path']=='config.json'))
        require(config['candidate_id'] == candidate and
                config['police_authority_verified'] is False,
                'Candidate config or authority claim differs')
        tuning = json.dumps(config.get('controller_tuning'),sort_keys=True)
        require(tuning not in seen_tunings and expected not in seen_constructions,
                'Candidate construction/tuning not distinct')
        seen_tunings.add(tuning)
        seen_constructions.add(expected)
        base = ROOT/'.runtime-work'/('c201084-officer_direction-rebound-'+candidate)
        source = Path(str(base)+'-compatibility')
        saved_path = Path(str(base)+'-saved')/'v0001/processing.json'
        compat_path = source/'compatibility.json'
        compat, saved = read(compat_path), read(saved_path)
        require(compat['passed'] is True and compat['candidate_id'] == candidate
                and compat['construction_sha256'] == expected and
                compat['runtime_manifest_sha256'] ==
                manifest['runtime_manifest_sha256'] and
                compat['negative_removed'] == 'police-officer-actor.jsonl' and
                'negative_case_source' in compat['checks'] and
                saved['passed'] is True and saved['recorded_only'] is True and
                saved['missing_evidence'] is False and
                saved['candidate_id'] == candidate and
                saved['native_revision']['construction_sha256'] == expected,
                'Exact compatibility or saved result differs: '+candidate)
        frames = [json.loads(line) for line in
                  (source/'video_frames.jsonl').read_text().splitlines()]
        rows = [json.loads(line) for line in
                (source/'police-officer-actor.jsonl').read_text().splitlines()]
        survey = read(source/'officer-survey-readback.json')
        require(len(frames) == len(rows) == 600 and
                len({row['carla_frame'] for row in frames}) == 600 and
                all(row['frame'] == frame['carla_frame'] and
                    row['video_frame'] == index and
                    row['officer_actor_id'] == survey['actor_id'] == 501 and
                    row['officer_type_id'] == survey['type_id'] and
                    row['source_kind'] == 'synthetic_native_sample' and
                    row['police_authority_verified'] is False and
                    row['direction_applicability_verified'] is False and
                    row['statutory_necessity_verified'] is False
                    for index, (row, frame) in enumerate(zip(rows, frames))),
                'Source frame/actor/claim differs: '+candidate)
        hashes = {}
        for source_name in ('officer-survey-readback.json',
                            'police-officer-actor.jsonl','video_frames.jsonl'):
            digest = sha(source/source_name)
            require(digest == saved['original_source_hashes'][source_name]
                    and digest == sha(saved_path.parent/'analysis'/source_name),
                    'Saved original changed: '+candidate+'/'+source_name)
            hashes[source_name] = digest
        if common_sources is None:
            common_sources = hashes
        else:
            require(hashes == common_sources, 'Fallback changed fixed actor source')
        require(all((source/(camera+'.mkv')).is_file() and
                    (saved_path.parent/'analysis'/(camera+'.mkv')).is_file()
                    for camera in CAMERAS), 'Four camera source missing')
        analysis = read(saved_path.parent/'analysis/analysis-report.json')
        result = read(saved_path.parent/'analysis/result.json')
        value = analysis['measurements']['officer_direction_context']['value']
        require(value['source_frames'] == 600 and
                all(value[key] is False for key in
                    ('police_authority_verified',
                     'direction_applicability_verified',
                     'statutory_necessity_verified')) and
                result['accepted'] is False and
                result['physical_acceptance_claimed'] is False and
                result['legal_verdict_claimed'] is False,
                'Saved analysis overclaims: '+candidate)
        receipt['candidates'][candidate] = {
            'construction_sha256':expected,
            'compatibility_sha256':sha(compat_path),
            'saved_sha256':sha(saved_path),
            'source_frames':600,
            'source_cameras':list(CAMERAS),
            'negative_source_rejected':True}
    receipt['passed'] = True
    output = HERE/'current-officer-rebound-audit.json'
    output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit(),sort_keys=True))
