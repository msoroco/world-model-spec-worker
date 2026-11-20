"""Inspect the exact four-candidate contrast CPU proof chain and source relation."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def insist(value, message):
    if not value:
        raise ValueError(message)


def audit():
    manifest_path = HERE/'draft-contrast-fallback-manifest.json'
    manifest = read(manifest_path)
    entry = manifest['cases'][0]
    contract = read(HERE/entry['measurement_contract'])
    insist(entry['case_id'] == HERE.name+'__contrast' and
           contract['case_id'] == entry['case_id'], 'Contrast case binding differs')
    constructions = {'primary': {'construction': entry['construction'],
                                 'construction_sha256': entry['construction_sha256']}}
    constructions.update({row['id']: row for row in entry['candidates']})
    insist(set(constructions) == set(NAMES) and
           len({row['construction_sha256'] for row in constructions.values()}) == 4,
           'Four distinct contrast constructions required')
    candidate_audit = {}
    for name in NAMES:
        selected = constructions[name]
        insist(sha(HERE/selected['construction']) == selected['construction_sha256'],
               'Construction differs: '+name)
        construction = read(HERE/selected['construction'])
        config = json.loads(next(row['content'] for row in construction['files']
                                 if row['path'] == 'config.json'))
        insist(config['case_id'] == entry['case_id'] and
               config['comparison_requested_value'] is False and
               config['candidate_id'] == name and
               (config['frames'], config['rate_hz'], config['duration_s']) == (600, 20, 30),
               'Candidate identity or clock differs: '+name)
        offline = ROOT/'.runtime-work'/f'c201084-update104-contrast-{name}-offline-2'
        selection = read(offline/'candidate-selection.json')
        insist(selection['candidate_id'] == name and
               selection['construction_sha256'] == selected['construction_sha256'] and
               selection['manifest_sha256'] == sha(manifest_path),
               'Offline selection differs: '+name)
        shutil.copyfile(offline/'offline.log', HERE/f'update104-{name}-offline.log')
        attempt = ROOT/'.runtime-work'/f'c201084-update104-contrast-{name}-compatibility-2'
        compatibility = read(HERE/f'update104-{name}-compatibility.log')
        insist(compatibility['passed'] is True and
               compatibility['candidate_id'] == name and
               compatibility['construction_sha256'] == selected['construction_sha256'] and
               compatibility['measurement_contract_sha256'] == sha(HERE/entry['measurement_contract']) and
               sorted(compatibility['measurement_keys']) ==
               sorted(row['output_key'] for row in contract['requirements']),
               'Compatibility binding differs: '+name)
        insist({'actual_analysis', 'native_validation', 'four_camera_sources',
                'lean_decoder', 'final_decode', 'negative_case_source',
                'selected_measurements'} <= set(compatibility['checks']),
               'Compatibility checks incomplete: '+name)
        sampled = compatibility['measurement_examples']['stop_exception_context']['value']
        insist(sampled['near_zero_with_authored_overlap_frames'] == 0 and
               sampled['near_zero_disjoint_frames'] == 598,
               'Contrast sampled outside-zone relation differs: '+name)
        insist(compatibility['negative_removed'] == contract['negative']['remove'][0] and
               compatibility['negative_log_sha256'] == sha(attempt/'negative-analysis.log') and
               contract['negative']['error_contains'] in
               (attempt/'negative-analysis.log').read_text(),
               'Missing-source negative differs: '+name)
        for stem in ('compatibility-analysis.log', 'negative-analysis.log'):
            shutil.copyfile(attempt/stem, HERE/f'update104-{name}-{stem}')
        saved = read(HERE/f'update104-{name}-saved.log')
        insist(saved['passed'] is True and saved['recorded_only'] is True and
               saved['candidate_id'] == name and saved['originals_preserved'] is True and
               saved['missing_evidence'] is False and
               saved['timestamp_joins']['passed'] is True and
               saved['timestamp_joins']['frames'] == 600 and
               not saved['physical_acceptance_claimed'] and
               not saved['legal_acceptance_claimed'],
               'Saved processing incomplete or acceptance claimed: '+name)
        for relative, checksum in saved['original_source_hashes'].items():
            insist(sha(attempt/relative) == checksum,
                   'Original source changed: '+name+'/'+relative)
        result = read(ROOT/'.runtime-work'/f'c201084-update104-contrast-{name}-saved'/
                      'v0001/analysis/result.json')
        insist(result['provenance_kind'] == 'synthetic_fixture' and
               result['diagnostic_fixture'] is True and not result['accepted'] and
               not result['physical_acceptance_claimed'] and
               not result['legal_verdict_claimed'] and
               result['realized_observables'][
                   'sampled_authored_zone_overlap_stopped_frames']['value'] == 0,
               'Synthetic result claimed acceptance or zone overlap: '+name)
        for kind, value in (('compatibility', compatibility), ('saved', saved)):
            path = HERE/f'update104-{name}-{kind}-receipt.json'
            path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')
        candidate_audit[name] = {
            'construction_sha256': selected['construction_sha256'],
            'offline_selection_sha256': sha(offline/'candidate-selection.json'),
            'compatibility_receipt_sha256': sha(HERE/f'update104-{name}-compatibility-receipt.json'),
            'saved_receipt_sha256': sha(HERE/f'update104-{name}-saved-receipt.json'),
            'source_count': len(saved['original_source_hashes'])}
    source_ref = ROOT/'.runtime-work/c201084-update102-finalizer-current-2'
    source_con = ROOT/'.runtime-work/c201084-update104-contrast-source'
    ref_actors = [json.loads(line) for line in (source_ref/'native-actors.jsonl').read_text().splitlines()]
    con_actors = [json.loads(line) for line in (source_con/'native-actors.jsonl').read_text().splitlines()]
    insist(len(ref_actors) == len(con_actors) == 600, 'Source comparison clock differs')
    for index, (ref, con) in enumerate(zip(ref_actors, con_actors)):
        shifted = json.loads(json.dumps(ref))
        shifted['ego_pose_xyz_m'][0] += 14
        for key in ('ego_body_vertices_xyz_m', 'following_body_vertices_xyz_m'):
            for vertex in shifted[key]:
                vertex[0] += 14
        insist(shifted == con, 'Source comparison changes another field at frame '+str(index))
    for name in ('native-survey-readback.json', 'video_frames.jsonl'):
        insist(sha(source_ref/name) == sha(source_con/name),
               'Source comparison context differs: '+name)
    ref_result = read(ROOT/'.runtime-work/c201084-update103-primary-saved/v0001/analysis/result.json')
    insist(ref_result['realized_observables'][
        'sampled_authored_zone_overlap_stopped_frames']['value'] == 598,
        'Reference diagnostic no longer reports inside-zone samples')
    return {'format': 'c201084-contrast-candidate-matrix-and-source-comparison-audit',
            'passed': True, 'case_id': entry['case_id'],
            'manifest_sha256': sha(manifest_path), 'candidates': candidate_audit,
            'controlled_source_shift_x_m': 14, 'sampled_reference_overlap_frames': 598,
            'sampled_contrast_overlap_frames': 0,
            'synthetic_only': True, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    output = audit()
    (HERE/'update104-contrast-candidate-audit.json').write_text(
        json.dumps(output, sort_keys=True, indent=2)+'\n')
    print(json.dumps(output, sort_keys=True))
