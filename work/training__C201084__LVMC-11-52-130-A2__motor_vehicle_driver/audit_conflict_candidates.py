"""Independent exact/source audit of four synthetic conflict CPU candidates."""
import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IDS = ('primary', 'fallback1', 'fallback2', 'fallback3')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('ego_pose', 'ego_speed', 'vehicle_stops_in_posted_fire_lane',
            'lead_traffic_relation')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(prefix):
    prefix = Path(prefix)
    manifest_path = HERE/'draft-conflict-fallback-manifest.json'
    manifest = read(manifest_path)
    case = HERE.name+'__conflict'
    entry, = manifest['cases']
    require(entry['case_id'] == case, 'Wrong conflict case')
    selections = {'primary': entry}
    selections.update({row['id']: row for row in entry['candidates']})
    require(set(selections) == set(IDS), 'Expected primary and three fallbacks')
    constructions = set()
    tunings = set()
    source_hashes = None
    audits = {}
    for ident in IDS:
        selection = selections[ident]
        construction_path = HERE/selection['construction']
        construction_sha = sha(construction_path)
        require(construction_sha == selection['construction_sha256'],
                ident+' construction hash differs')
        constructions.add(construction_sha)
        construction = read(construction_path)
        config = json.loads(next(row['content'] for row in construction['files']
                                 if row['path'] == 'config.json'))
        require(config['candidate_id'] == ident and
                config['case_id'] == case and config['frames'] == 600 and
                config['rate_hz'] == 20 and len(config['cameras']) == 4,
                ident+' exact config differs')
        tunings.add(json.dumps(config.get('conflict_controller_tuning'),
                               sort_keys=True))
        root = ROOT/'.runtime-work'/f'{prefix}-{ident}'
        offline = root.with_name(root.name+'-offline')
        compat = root.with_name(root.name+'-compatibility')
        saved = root.with_name(root.name+'-saved')/'v0001'
        for path in (offline, compat, saved):
            require(path.is_dir(), ident+' missing proof directory')
        offline_selection = read(offline/'candidate-selection.json')
        compat_selection = read(compat/'candidate-selection.json')
        for selected in (offline_selection, compat_selection):
            require(selected['candidate_id'] == ident and
                    selected['case_id'] == case and
                    selected['construction_sha256'] == construction_sha and
                    selected['manifest_sha256'] == sha(manifest_path),
                    ident+' exact selection differs')
        compatibility = read(compat/'compatibility.json')
        require(compatibility['passed'] is True and
                compatibility['candidate_id'] == ident and
                compatibility['construction_sha256'] == construction_sha and
                'negative_case_source' in compatibility['checks'],
                ident+' compatibility proof differs')
        processing = read(saved/'processing.json')
        require(processing['passed'] is True and
                processing['recorded_only'] is True and
                processing['originals_preserved'] is True and
                processing['missing_evidence'] is False and
                processing['physical_acceptance_claimed'] is False and
                processing['legal_acceptance_claimed'] is False and
                processing['analysis_revision']['construction_sha256'] ==
                    construction_sha,
                ident+' saved processing proof differs')
        analysis = saved/'analysis'
        result, report = read(analysis/'result.json'), read(analysis/'analysis-report.json')
        require(result['accepted'] is False and
                result['physical_acceptance_claimed'] is False and
                result['legal_verdict_claimed'] is False and
                result['measured_values']['source_frames'] == 600 and
                result['measured_values']['statutory_necessity_verified'] is False and
                result['measured_values']['lead_ahead_frames'] == 600 and
                result['measured_values']['brake_request_frames'] == 600 and
                report['analysis_complete'] is True and
                report['diagnostic_fixture'] is True,
                ident+' saved result overclaims or lacks lead samples')
        for name in CHANNELS:
            require(len((analysis/'channels'/(name+'.jsonl')).read_text().splitlines()) == 600,
                    ident+' source-derived channel length differs: '+name)
        hashes = {name: sha(analysis/name) for name in
                  ('native-actors.jsonl','video_frames.jsonl',
                   'native-survey-readback.json',
                   *[camera+'.mkv' for camera in CAMERAS])}
        require(all(result['physical_checks'][key]['sources'][name] == checksum
                    for key in ('setup','target','maneuver')
                    for name, checksum in hashes.items()),
                ident+' physical-check source hashes differ')
        if source_hashes is None:
            source_hashes = hashes
        require(hashes == source_hashes,
                ident+' diagnostic source changed across candidate selection')
        audits[ident] = {
            'construction_sha256': construction_sha,
            'offline_selection_sha256': sha(offline/'candidate-selection.json'),
            'compatibility_receipt_sha256': sha(compat/'compatibility.json'),
            'saved_receipt_sha256': sha(saved/'processing.json'),
            'source_frames': 600,
            'lead_ahead_frames': 600,
            'brake_request_frames': 600}
    require(len(constructions) == len(IDS) and len(tunings) == len(IDS),
            'Conflict fallback constructions or controller tunings repeat')
    return {'case_id': case, 'manifest_sha256': sha(manifest_path),
            'candidate_count': len(IDS), 'candidates': audits,
            'source_sha256': source_hashes,
            'diagnostic_only': True,
            'original_native_verified': False,
            'statutory_necessity_verified': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', default='c201084-update107')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.prefix)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'candidate_count': result['candidate_count'],
                      'diagnostic_only': result['diagnostic_only'],
                      'manifest_sha256': result['manifest_sha256']}))
